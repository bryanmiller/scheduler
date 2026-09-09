# Copyright (c) 2016-2025 Association of Universities for Research in Astronomy, Inc. (AURA)
# For license information see LICENSE or https://opensource.org/licenses/BSD-3-Clause

import asyncio
import os
import time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from lucupy.minimodel.site import ALL_SITES, Site
from lucupy.observatory.abstract import ObservatoryProperties
from lucupy.observatory.gemini import GeminiProperties


from definitions import ROOT_DIR
from scheduler.core.builder.modes import SchedulerModes
from scheduler.core.components.ranker import RankerParameters
from scheduler.engine import SchedulerParameters, Engine
from scheduler.services import logger_factory
from scheduler.services.sight.database.connection import init_db_engine

_logger = logger_factory.create_logger(__name__)

def main(*,
    programs_ids: Path = Path(ROOT_DIR) / 'scheduler' / 'data' / 'program_ids.txt') -> None:

    # Set lucupy to Gemini
    ObservatoryProperties.set_properties(GeminiProperties)
    asyncio.run(init_db_engine())

    # Parsed program file (this replaces the program picker from Schedule)
    with open(programs_ids, 'r') as file:
        programs_list = [line.strip() for line in file if line.strip()[0] != '#']
    # programs_list = ['GS-2018B-Q-112', 'GS-2018B-Q-113', 'GS-2018B-Q-127', 'GS-2018B-Q-133']
    # programs_list = ['GN-2018B-Q-132',]

    # Create Parameters
    # params = SchedulerParameters(start=datetime.fromisoformat("2018-10-04 08:00:00").replace(tzinfo=ZoneInfo("UTC")),
    #                              end=datetime.fromisoformat("2018-10-10 08:00:00").replace(tzinfo=ZoneInfo("UTC")),
    # GPIES and GN classical
    # params = SchedulerParameters(start=datetime.fromisoformat("2018-08-06 08:00:00").replace(tzinfo=ZoneInfo("UTC")),
    #                              end=datetime.fromisoformat("2018-08-20 08:00:00").replace(tzinfo=ZoneInfo("UTC")),
    # params = SchedulerParameters(start=datetime.fromisoformat("2018-11-02 08:00:00").replace(tzinfo=ZoneInfo("UTC")),
    #                              end=datetime.fromisoformat("2018-11-16 08:00:00").replace(tzinfo=ZoneInfo("UTC")),
    # params = SchedulerParameters(start=datetime.fromisoformat("2018-08-02 08:00:00").replace(tzinfo=ZoneInfo("UTC")),
    #                             end=datetime.fromisoformat("2019-02-01 08:00:00").replace(tzinfo=ZoneInfo("UTC")),
    # `Alopeke
    params = SchedulerParameters(start=datetime.fromisoformat("2018-10-19 08:00:00").replace(tzinfo=ZoneInfo("UTC")),
                                end=datetime.fromisoformat("2018-10-31 08:00:00").replace(tzinfo=ZoneInfo("UTC")),
                                 # sites=ALL_SITES,
                                 sites=[Site.GN],
    #                              sites=[Site.GS],
                                 mode=SchedulerModes.VALIDATION,
                                 ranker_parameters=RankerParameters(),
                                 semester_visibility=False,
                                 num_nights_to_schedule=4,
                                 programs_list=programs_list,
                                 use_local_visibility=True)
    engine = Engine(params)
    plan_summary, timelines = engine.schedule()
    # File output for future results comparison
    outpath = os.path.join(os.environ['HOME'], 'gemini', 'sciops', 'softdevel', 'Queue_planning', 'sched_output')
    # timelines.display(output=os.path.join(outpath, 'gn_1min_s20180801_184_20260817.txt'))
    # timelines.display(output=os.path.join(outpath, 'gs_1min_s20180801_48_20260827_stitched.txt'), stitched=True)
    # timelines.display(output=os.path.join(outpath, 'gs_1min_s20180801_48_20260826.txt'), stitched=False)

    # timelines.display()
    timelines.display(stitched=False)
    print(plan_summary)

if __name__ == '__main__':
    t0 = time.time()
    # programs_ids = Path(ROOT_DIR) / 'scheduler/data' / 'program_ids.txt'
    # programs_ids = Path(ROOT_DIR) / 'scheduler/data' / 'program_ids_gn.redis.txt'
    # programs_ids = Path(ROOT_DIR) / 'scheduler/data' / 'program_ids_gs.redis.txt'
    programs_ids = Path(ROOT_DIR) / 'scheduler/data' / 'program_ids_202609.txt'
    main(programs_ids=programs_ids)
    print(f'Completed in {(time.time() - t0) / 60.} min')
