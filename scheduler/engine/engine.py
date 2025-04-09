# Copyright (c) 2016-2024 Association of Universities for Research in Astronomy, Inc. (AURA)
# For license information see LICENSE or https://opensource.org/licenses/BSD-3-Clause

from typing import Dict, Optional, Tuple, Generator

import time
import numpy as np
from lucupy.minimodel import Site, NightIndex, VariantSnapshot, TimeslotIndex
from lucupy.timeutils import time2slots

from .params import SchedulerParameters
from .scp import SCP

from scheduler.core.builder.modes import dispatch_with
from scheduler.core.builder import Blueprints
from scheduler.core.components.changemonitor import ChangeMonitor, TimeCoordinateRecord
from scheduler.core.components.ranker import DefaultRanker
from scheduler.core.eventsqueue import EventQueue, EveningTwilightEvent, WeatherChangeEvent, MorningTwilightEvent, Event
from scheduler.core.eventsqueue.nightchanges import NightlyTimeline
from scheduler.core.plans import Plans
from scheduler.core.sources import Sources
from scheduler.core.statscalculator import StatCalculator
from scheduler.services import logger_factory


__all__ = [
    'Engine'
]

from ..core.statscalculator.run_summary import RunSummary

_logger = logger_factory.create_logger(__name__)


class Engine:

    def __init__(self, params: SchedulerParameters):
        self.params = params
        self.sources = Sources()
        self.queue = None
        self.change_monitor = None

    def _schedule(self,
                  scp: SCP,
                  nightly_timeline: NightlyTimeline,
                  site: Site,
                  night_idx: NightIndex,
                  initial_variants: Dict[Site, Dict[NightIndex, Optional[VariantSnapshot]]],
                  next_update: Dict[Site, Optional[TimeCoordinateRecord]]):

        """
        This is the scheduling process. It handles different types of events with the ChangeMonitor and
        the SCP creation of plans, which are both registered in a Nightly Timeline that saves the plans
        generated by event.

        The NightlyTimeline is pass as parameter so the creating can be handle outside this process.
        """

        site_name = site.site_name
        time_slot_length = scp.collector.time_slot_length.to_datetime()
        night_indices = np.array([night_idx])
        # tr0 = time.time()
        ranker = DefaultRanker(scp.collector, night_indices, self.params.sites, params=self.params.ranker_parameters)
        # print(f'\tRanker completed in {(time.time() - tr0)} sec')

        # Plan and event queue management.
        plans: Optional[Plans] = None
        events_by_night = self.queue.get_night_events(night_idx, site)
        if events_by_night.is_empty():
            raise RuntimeError(f'No events for site {site_name} for night {night_idx}.')

        # We need the start of the night for checking if an event has been reached.
        # Next update indicates when we will recalculate the plan.
        # tne0 = time.time()
        night_events = scp.collector.get_night_events(site)
        # print(f'\tNight events returned in {(time.time() - tne0)} sec')

        night_start = night_events.twilight_evening_12[night_idx].to_datetime(site.timezone)
        next_update[site] = None

        current_timeslot: TimeslotIndex = TimeslotIndex(0)
        next_event: Optional[Event] = None
        next_event_timeslot: Optional[TimeslotIndex] = None
        night_done = False

        # Set the initial variant for the site for the night. This may have been set above by weather
        # information obtained before or at the start of the night, and if not, then the lookup will give None,
        # which will reset to the default values as defined in the Selector.
        _logger.debug(f'Resetting {site_name} weather to initial values for night...')
        scp.selector.update_site_variant(site, initial_variants[site][night_idx])

        while not night_done:
            # If our next update isn't done, and we are out of events, we're missing the morning twilight.
            if next_event is None and events_by_night.is_empty():
                raise RuntimeError(f'No morning twilight found for site {site_name} for night {night_idx}.')

            if next_event_timeslot is None or current_timeslot >= next_event_timeslot:

                if not events_by_night.has_more_events():
                    # Check if there are no more events so it won't enter the loop behind
                    break
                # Stop if there are no more events.
                while events_by_night.has_more_events():
                    top_event = events_by_night.top_event()
                    top_event_timeslot = top_event.to_timeslot_idx(night_start, time_slot_length)

                    # TODO: Check this over to make sure if there is an event now, it is processed.
                    # If we don't know the next event timeslot, set it.

                    if next_event_timeslot is None:
                        next_event_timeslot = top_event_timeslot
                        next_event = top_event

                    if current_timeslot > next_event_timeslot:
                        # Things happening after the EveTwilight fall here as the current_timeslot start at 0.
                        # We could handle stuff
                        _logger.warning(f'Received event for {site_name} for night idx {night_idx} at timeslot '
                                        f'{next_event_timeslot} < current time slot {current_timeslot}.')

                    # The next event happens in the future, so record that time.
                    if top_event_timeslot > current_timeslot:
                        next_event_timeslot = top_event_timeslot
                        break

                    # We have an event that occurs at this time slot and is in top_event, so pop it from the
                    # queue and process it.
                    events_by_night.pop_next_event()
                    _logger.debug(
                        f'Received event for site {site_name} for night idx {night_idx} to be processed '
                        f'at timeslot {next_event_timeslot}: {next_event.__class__.__name__}')

                    # Process the event: find out when it should occur.
                    # If there is no next update planned, then take it to be the next update.
                    # If there is a next update planned, then take it if it happens before the next update.
                    # Process the event to find out if we should recalculate the plan based on it and when.
                    time_record = self.change_monitor.process_event(site, top_event, plans, night_idx)
                    if time_record is not None:
                        # In the case that:
                        # * there is no next update scheduled; or
                        # * this update happens before the next update
                        # then set to this update.
                        if next_update[site] is None or time_record.timeslot_idx <= next_update[site].timeslot_idx:
                            next_update[site] = time_record
                            _logger.debug(f'Next update for site {site_name} scheduled at '
                                          f'timeslot {next_update[site].timeslot_idx}')

            # If there is a next update, and we have reached its time, then perform it.
            # This is where we perform time accounting (if necessary), get a selection, and create a plan.
            if next_update[site] is not None and current_timeslot >= next_update[site].timeslot_idx:
                # Remove the update and perform it.
                update = next_update[site]
                next_update[site] = None

                if current_timeslot > update.timeslot_idx:
                    _logger.warning(
                        f'Plan update at {site.name} for night {night_idx} for {update.event.__class__.__name__}'
                        f' scheduled for timeslot {update.timeslot_idx}, but now timeslot is {current_timeslot}.')

                # We will update the plan up until the time that the update happens.
                # If this update corresponds to the night being done, then use None.
                if update.done:
                    end_timeslot_bounds = {}
                else:
                    end_timeslot_bounds = {site: update.timeslot_idx}

                # If there was an old plan and time accounting is to be done, then process it.
                if plans is not None and update.perform_time_accounting:
                    if update.done:
                        ta_description = 'for rest of night.'
                    else:
                        ta_description = f'up to timeslot {update.timeslot_idx}.'
                    _logger.debug(f'Time accounting: site {site_name} for night {night_idx} {ta_description}')
                    # ta0 = time.time()
                    scp.collector.time_accounting(plans=plans,
                                                  sites=frozenset({site}),
                                                  end_timeslot_bounds=end_timeslot_bounds)
                    # print(f'\tTA completed in {(time.time() - ta0)} sec')

                    if update.done:
                        # In the case of the morning twilight, which is the only thing that will
                        # be represented here by update.done, we add the final plan that shows all the
                        # observations that were actually visited in that night.
                        final_plan = nightly_timeline.get_final_plan(NightIndex(night_idx), site)
                        nightly_timeline.add(NightIndex(night_idx),
                                             site,
                                             current_timeslot,
                                             update.event,
                                             final_plan)

                # Get a new selection and request a new plan if the night is not done.
                if not update.done:
                    _logger.debug(f'Retrieving selection for {site_name} for night {night_idx} '
                                  f'starting at time slot {current_timeslot}.')

                    # If the site is blocked, we do not perform a selection or optimizer run for the site.
                    if self.change_monitor.is_site_unblocked(site):
                        tvm0 = time.time()
                        print(f'\tscp.run start')
                        plans = scp.run(site, night_indices, current_timeslot, ranker)
                        print(f'\t\tscp.run completed in {(time.time() - tvm0)} sec')
                        nightly_timeline.add(NightIndex(night_idx),
                                             site,
                                             current_timeslot,
                                             update.event,
                                             plans[site])
                    else:
                        # The site is blocked.
                        _logger.debug(
                            f'Site {site_name} for {night_idx} blocked at timeslot {current_timeslot}.')
                        nightly_timeline.add(NightIndex(night_idx),
                                             site,
                                             current_timeslot,
                                             update.event,
                                             None)

                # Update night_done based on time update record.
                night_done = update.done

            # We have processed all events for this timeslot and performed an update if necessary.
            # Advance the current time.
            current_timeslot += 1

        # Process any events still remaining, with the intent of unblocking faults and weather closures.
        eve_twi_time = night_events.twilight_evening_12[night_idx].to_datetime(site.timezone)
        while events_by_night.has_more_events():
            event = events_by_night.pop_next_event()
            event.to_timeslot_idx(eve_twi_time, time_slot_length)
            _logger.warning(f'Site {site_name} on night {night_idx} has event after morning twilight: {event}')
            self.change_monitor.process_event(site, event, None, night_idx)

            # Timeslot will be after final timeslot because this event is scheduled later.
            nightly_timeline.add(NightIndex(night_idx), site, current_timeslot, event, None)

        # The site should no longer be blocked.
        if not self.change_monitor.is_site_unblocked(site):
            _logger.warning(f'Site {site_name} is still blocked after all events on night {night_idx} processed.')

    def build(self) -> SCP:
        """
        Creates a Scheduler Core Pipeline based on the parameters.
        Also initialize both the Event Queue and Change Monitor, both needed for the scheduling process.
        """

        # Create event queue to handle incoming events.
        self.queue = EventQueue(self.params.night_indices, self.params.sites)

        # Create builder based in the mode to create SCP
        builder = dispatch_with(self.params.mode, self.sources, self.queue)

        t0 = time.time()
        collector = builder.build_collector(start=self.params.start,
                                            end=self.params.end_vis,
                                            num_of_nights=self.params.num_nights_to_schedule,
                                            sites=self.params.sites,
                                            semesters=self.params.semesters,
                                            blueprint=Blueprints.collector,
                                            program_list=self.params.programs_list)
        t1 = time.time()
        print(f'Collector built in {(t1 - t0) / 60.} min')

        selector = builder.build_selector(collector=collector,
                                          num_nights_to_schedule=self.params.num_nights_to_schedule,
                                          blueprint=Blueprints.selector)
        # t2 = time.time()
        # print(f'Selector built in {(t2 - t1)} sec')

        optimizer = builder.build_optimizer(Blueprints.optimizer)
        # t3 = time.time()
        # print(f'Optimizer built in {(t3 - t2)} sec')
        # ranker = DefaultRanker(collector,
        #                       self.params.night_indices,
        #                       self.params.sites,
        #                       params=self.params.ranker_parameters)

        # Create the ChangeMonitor and keep track of when we should recalculate the plan for each site.
        self.change_monitor = ChangeMonitor(collector=collector, selector=selector)
        # t4 = time.time()
        # print(f'Change monitor created in {(t4 - t3)} sec')

        return SCP(collector, selector, optimizer)

    def setup(self, scp: SCP) -> Dict[Site, Dict[NightIndex, Optional[VariantSnapshot]]]:
        """
        This process is needed before the scheduling process can occur.
        It handles the initial weather conditions, the setup for both twilights,
        the fault handling and other events to be added to the queue.
        Returns the initial weather variations for each site and for each night.
        """
        # TODO: The weather process might want to be done separately from the fulfillment of the queue.
        # TODO: specially since those process in the PRODUCTION mode are going to be different.

        sites = self.params.sites
        night_indices = self.params.night_indices
        time_slot_length = scp.collector.time_slot_length.to_datetime()

        # Initial weather conditions for a night.
        # These can occur if a weather reading is taken from timeslot 0 or earlier on a night.
        initial_variants = {site: {night_idx: None for night_idx in night_indices} for site in sites}

        # Add the twilight events for every night at each site.
        # The morning twilight will force time accounting to be done on the last generated plan for the night.
        for site in sites:
            night_events = scp.collector.get_night_events(site)
            for night_idx in night_indices:
                # this would be probably because when the last time the resource pickle was created, it was winter time
                # or different.
                eve_twi_time = night_events.twilight_evening_12[night_idx].to_datetime(site.timezone)
                eve_twi = EveningTwilightEvent(site=site, time=eve_twi_time, description='Evening 12° Twilight')
                self.queue.add_event(night_idx, site, eve_twi)

                # Get the weather events for the site for the given night date.
                night_date = eve_twi_time.date()
                morn_twi_time = night_events.twilight_morning_12[night_idx].to_datetime(
                    site.timezone) - time_slot_length
                # morn_twi_slot = time2slots(time_slot_length, morn_twi_time - eve_twi_time)
                morn_twi_slot = night_events.num_timeslots_per_night[night_idx]

                # Get initial conditions for the nights
                initial_variants[site][night_idx] = scp.collector.sources.origin.env.get_initial_conditions(site,
                                                                                                            night_date)

                # Get the weather events for the site for the given night date.
                # Get the VariantSnapshots for the times of the night where the variant changes.
                variant_changes_dict = scp.collector.sources.origin.env.get_variant_changes_for_night(site, night_date)
                for variant_datetime, variant_snapshot in variant_changes_dict.items():
                    variant_timeslot = time2slots(time_slot_length, variant_datetime - eve_twi_time)

                    # If the variant happens before or at the first time slot, we set the initial variant for the night.
                    # The closer to the first time slot, the more accurate, and the ordering on them will overwrite
                    # the previous values.
                    if variant_timeslot <= 0:
                        _logger.debug(f'WeatherChange for site {site.name}, night {night_idx}, occurs before '
                                      '0: ignoring.')
                        continue

                    if variant_timeslot >= morn_twi_slot:
                        _logger.debug(f'WeatherChange for site {site.name}, night {night_idx}, occurs after '
                                      f'{morn_twi_slot}: ignoring.')
                        continue

                    variant_datetime_str = variant_datetime.strftime('%Y-%m-%d %H:%M')
                    weather_change_description = (f'Weather change at {site.name}, {variant_datetime_str}: '
                                                  f'IQ -> {variant_snapshot.iq.name}, '
                                                  f'CC -> {variant_snapshot.cc.name}')
                    weather_change_event = WeatherChangeEvent(site=site,
                                                              time=variant_datetime,
                                                              description=weather_change_description,
                                                              variant_change=variant_snapshot)
                    self.queue.add_event(night_idx, site, weather_change_event)

                # Process the unexpected closures for the night at the site -> Weather loss events
                closure_set = scp.collector.sources.origin.resource.get_unexpected_closures(site, night_date)
                for closure in closure_set:
                    closure_start, closure_end = closure.to_events()
                    self.queue.add_event(night_idx, site, closure_start)
                    self.queue.add_event(night_idx, site, closure_end)

                # Process the fault reports for the night at the site.
                faults_set = scp.collector.sources.origin.resource.get_faults(site, night_date)
                for fault in faults_set:
                    fault_start, fault_end = fault.to_events()
                    self.queue.add_event(night_idx, site, fault_start)
                    self.queue.add_event(night_idx, site, fault_end)

                # Process the ToO activation for the night at the site.

                too_set = scp.collector.sources.origin.resource.get_toos(site, night_date)
                for too in too_set:
                    too_event = too.to_event()
                    self.queue.add_event(night_idx, site, too_event)

                morn_twi = MorningTwilightEvent(site=site, time=morn_twi_time, description='Morning 12° Twilight')
                self.queue.add_event(night_idx, site, morn_twi)

                # TODO: If any InterruptionEvents occur before twilight, block the site with the event.

        return initial_variants

    def run(self) -> Tuple[RunSummary, NightlyTimeline]:
        """
        Run sequentially for all nights.
        """

        nightly_timeline = NightlyTimeline()
        scp = self.build()
        # tv0 = time.time()
        initial_variants = self.setup(scp)
        # print(f'Initial variants created in {(time.time() - tv0) / 60.} min')

        next_update = {site: None for site in self.params.sites}

        tn0 = time.time()
        for night_idx in sorted(self.params.night_indices):
            print(f'Night {night_idx} start')
            for site in sorted(self.params.sites, key=lambda site: site.name):
                self._schedule(scp, nightly_timeline, site, night_idx, initial_variants, next_update)
            tn1 = time.time()
            print(f'Night {night_idx} scheduled in {(tn1 - tn0) / 60.} min')
            tn0 = tn1

        # TODO: Add plan summary to nightlyTimeline
        run_summary = StatCalculator.calculate_timeline_stats(nightly_timeline,
                                                              self.params.night_indices,
                                                              self.params.sites, scp.collector)

        return run_summary, nightly_timeline
