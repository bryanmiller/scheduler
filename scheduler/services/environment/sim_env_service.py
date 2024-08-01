# Copyright (c) 2016-2024 Association of Universities for Research in Astronomy, Inc. (AURA)
# For license information see LICENSE or https://opensource.org/licenses/BSD-3-Clause

import bz2
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Final, FrozenSet

import astropy.units as u
import pandas as pd
from astropy.coordinates import Angle
from lucupy.minimodel import ALL_SITES, CloudCover, ImageQuality, Site, VariantSnapshot

from definitions import ROOT_DIR
from scheduler.services import logger_factory
from scheduler.services.abstract import ExternalService

logger = logger_factory.create_logger(__name__)


class SimEnvService(ExternalService):
    """
    This is a mock Resource service used for GPP simulation purposes.
    """

    # The columns used from the pandas dataframe.
    _night_time_stamp_col: Final[str] = 'Local_Night'
    _local_time_stamp_col: Final[str] = 'Local_Time'
    _cc_col: Final[str] = 'raw_cc'
    _iq_col: Final[str] = 'raw_iq'
    _wind_speed_col: Final[str] = 'WindSpeed'
    _wind_dir_col: Final[str] = 'WindDir'

    def __init__(self, sites: FrozenSet[Site] = ALL_SITES):
        """
        Read in the pandas data from the data files.
        """
        self._sites = sites

        # The data per site. The pandas data structure is too complicated to fully represent.
        self._site_data: Dict[Site, pd.DataFrame] = {}

        path = Path(ROOT_DIR) / 'scheduler' / 'services' / 'environment' / 'data' / 'simulation'
        for site in self._sites:
            site_lc = site.name.lower()
            input_file_path = path / f'{site_lc}_weather_data.csv'

            logger.debug(f'Processing weather data for {site.name}...')
            df = pd.read_csv(input_file_path)
            df[SimEnvService._night_time_stamp_col] = pd.to_datetime(df[SimEnvService._night_time_stamp_col])
            df[SimEnvService._local_time_stamp_col] = pd.to_datetime(df[SimEnvService._local_time_stamp_col])
            self._site_data[site] = df
            logger.debug(f'Weather data for {site.name} read in: {len(self._site_data[site])} rows.')

    @staticmethod
    def _convert_to_variant(row) -> (datetime, VariantSnapshot):
        """
        Given a pandas row from the weather data, turn it into a Variant object.
        """
        timestamp = row[SimEnvService._local_time_stamp_col].to_pydatetime()
        iq = ImageQuality(row[SimEnvService._iq_col])
        cc = CloudCover(row[SimEnvService._cc_col])
        wind_dir = Angle(row[SimEnvService._wind_dir_col], unit=u.deg)
        wind_spd = row[SimEnvService._wind_speed_col] * (u.m / u.s)

        variant_change = VariantSnapshot(iq=iq,
                                         cc=cc,
                                         wind_dir=wind_dir,
                                         wind_spd=wind_spd)
        return timestamp, variant_change

    def get_variant_changes_for_night(self,
                                      site: Site,
                                      night_date: date) -> Dict[datetime, VariantSnapshot]:
        """
        Return the weather variant.
        This should be site-based and time-based.
        times should be a contiguous set of times, but we do not force this.
        """
        df = self._site_data[site]
        # Get all the entries for the given night date.
        filtered_df = df[df[SimEnvService._night_time_stamp_col].dt.date == night_date]
        variant_list = filtered_df.apply(SimEnvService._convert_to_variant, axis=1).values.tolist()
        return {dt: v for dt, v in variant_list}
