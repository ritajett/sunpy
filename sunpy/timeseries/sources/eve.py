import os
import codecs
from os.path import basename
from collections import OrderedDict

import numpy as np
from pandas import DataFrame, to_datetime
from pandas.io.parsers import read_csv

import astropy.units as u
from astropy.time import TimeDelta
from astropy.time import Time

import sunpy.io
from sunpy.time import parse_time
from sunpy.timeseries.timeseriesbase import GenericTimeSeries
from sunpy.util.decorators import deprecate_positional_args_since
from sunpy.util.exceptions import warn_deprecated
from sunpy.util.metadata import MetaDict
from sunpy.visualization import peek_show

__all__ = ['EVESpWxTimeSeries', 'ESPTimeSeries', 'EVEL3TimeSeries']


class ESPTimeSeries(GenericTimeSeries):
    """
    SDO EVE/ESP Level 1 data.

    The Extreme ultraviolet Spectro-Photometer (ESP) is an irradiance instrument
    which is part of the Extreme ultraviolet Variability Experiment (EVE) on board
    SDO. ESP provides high time cadence (0.25s) EUV irradiance measurements in five
    channels, one soft X-ray and 4 EUV. The first four orders of the diffraction grating
    gives measurements centered on 18nm, 26nm, 30nm and 36nm. The zeroth order (obtained
    by 4 photodiodes) provides the soft X-ray measurements from 0.1-7nm.

    The ESP level 1 fits files are fully calibrated. The TimeSeries object created from
    an ESP fits file will contain 4 columns namely:

        * 'QD' - sum of 4 quad diodes, this is the soft X-ray measurements 0.1-7nm
        * 'CH_18' - EUV irradiance 18nm
        * 'CH_26' - EUV irradiance 26nm
        * 'CH_30' - EUV irradiance 30nm
        * 'CH_36' - EUV irradiance 36nm

    References
    ----------
    * `SDO Mission Homepage <https://sdo.gsfc.nasa.gov/>`__
    * `EVE Homepage <http://lasp.colorado.edu/home/eve/>`__
    * `README ESP data <http://lasp.colorado.edu/eve/data_access/evewebdata/products/level1/esp/EVE_ESP_L1_V6_README.pdf>`__
    * `ESP lvl1 data <http://lasp.colorado.edu/eve/data_access/evewebdata/misc/eve_calendars/calendar_level1_2018.html>`__
    * `ESP instrument paper <https://doi.org/10.1007/s11207-009-9485-8>`__

    Notes
    -----
    The 36nm channel demonstrates a significant noise and it is not recommended to be
    used for short-time observations of solar irradiance.
    """

    _source = 'esp'
    _url = "http://lasp.colorado.edu/home/eve/"

    def plot(self, axes=None, columns=None, **kwargs):
        """
        Plots the EVE ESP Level 1 timeseries data.

        Parameters
        ----------
        axes : numpy.ndarray of `matplotlib.axes.Axes`, optional
            The axes on which to plot the TimeSeries.
        columns : list[str], optional
            If provided, only plot the specified columns.
        **kwargs : `dict`
            Additional plot keyword arguments that are handed to `pandas.DataFrame.plot`.

        Returns
        -------
        array of `~matplotlib.axes.Axes`
            The plot axes.
        """
        axes, columns = self._setup_axes_columns(axes, columns, subplots=True)
        column_names = {"QD": "Flux \n 0.1-7nm", "CH_18": "Flux \n 18nm",
                        "CH_26": "Flux \n 26nm", "CH_30": "Flux \n 30nm", "CH_36": "Flux \n 36nm"}

        for i, name in enumerate(self.to_dataframe()[columns]):
            axes[i].plot(self._data[name],
                         label=name)
            axes[i].set_ylabel(column_names[name])
            axes[i].legend(loc="upper right")
        axes[-1].set_xlim(self._data.index[0], self._data.index[-1])
        self._setup_x_axis(axes)
        return axes

    @peek_show
    @deprecate_positional_args_since("4.1")
    def peek(self, *, title="EVE/ESP Level 1", columns=None, **kwargs):
        """
        Displays the EVE ESP Level 1 timeseries data by calling
        `~sunpy.timeseries.sources.eve.ESPTimeSeries.plot`.

        Parameters
        ----------
        title : `str`, optional
            The title of the plot. Defaults to "EVE/ESP Level 1".
        columns : list[str], optional
            If provided, only plot the specified columns.
        **kwargs : `dict`
            Additional plot keyword arguments that are handed to `pandas.DataFrame.plot`.
        """
        axes = self.plot(columns=columns, **kwargs)
        axes[0].set_title(title)
        fig = axes[0].get_figure()
        fig.tight_layout()
        fig.subplots_adjust(hspace=0.05)
        return fig

    @classmethod
    def _parse_file(cls, filepath):
        """
        Parses a EVE ESP level 1 data.
        """
        hdus = sunpy.io.read_file(filepath)
        return cls._parse_hdus(hdus)

    @classmethod
    def _parse_hdus(cls, hdulist):
        header = MetaDict(OrderedDict(hdulist[0].header))
        # Adding telescope and instrument to MetaData
        header.update({'TELESCOP': hdulist[1].header['TELESCOP'].split()[0]})
        header.update({'INSTRUME': hdulist[1].header['INSTRUME'].split()[0]})

        start_time = parse_time(hdulist[1].header['T_OBS'])
        times = start_time + TimeDelta(hdulist[1].data['SOD']*u.second)

        colnames = ['QD', 'CH_18', 'CH_26', 'CH_30', 'CH_36']

        all_data = [hdulist[1].data[x] for x in colnames]
        data = DataFrame(np.array(all_data).T, index=times.isot.astype(
            'datetime64'), columns=colnames)
        data.sort_index(inplace=True)

        units = OrderedDict([('QD', u.W/u.m**2),
                             ('CH_18', u.W/u.m**2),
                             ('CH_26', u.W/u.m**2),
                             ('CH_30', u.W/u.m**2),
                             ('CH_36', u.W/u.m**2)])

        return data, header, units

    @classmethod
    def is_datasource_for(cls, **kwargs):
        """
        Determines if header corresponds to an EVE image.
        """
        if kwargs.get('source', ''):
            return kwargs.get('source', '').lower().startswith(cls._source)
        if 'meta' in kwargs.keys():
            return (kwargs['meta'].get('TELESCOP', '').endswith('SDO/EVE')) & \
                (kwargs['meta'].get('INSTRUME', '').endswith('EVE_ESP') )


class EVESpWxTimeSeries(GenericTimeSeries):
    """
    SDO EVE LightCurve for level 0CS data.

    The Extreme Ultraviolet Variability Experiment (EVE) is an instrument on board the Solar Dynamics Observatory (SDO).
    The EVE instrument is designed to measure the solar extreme ultraviolet (EUV) irradiance.
    The EUV radiation includes the 0.1-105 nm range, which provides the majority
    of the energy for heating Earth's thermosphere and creating Earth's ionosphere (charged plasma).

    EVE includes several irradiance instruments:

    * The Multiple EUV Grating Spectrographs (MEGS)-A is a grazing- incidence spectrograph
      that measures the solar EUV irradiance in the 5 to 37 nm range with 0.1-nm resolution,
    * The MEGS-B is a normal-incidence, dual-pass spectrograph that measures the solar EUV
      irradiance in the 35 to 105 nm range with 0.1-nm resolution.

    Level 0CS data is primarily used for space weather.
    It is provided near real-time and is crudely calibrated 1-minute averaged broadband irradiances from ESP and MEGS-P broadband.
    For other levels of EVE data, use `~sunpy.net.Fido`, with ``sunpy.net.attrs.Instrument('eve')``.

    Data is available starting on 2010/03/01.

    Examples
    --------
    >>> import sunpy.timeseries
    >>> import sunpy.data.sample  # doctest: +REMOTE_DATA
    >>> eve = sunpy.timeseries.TimeSeries(sunpy.data.sample.EVE_TIMESERIES, source='EVE')  # doctest: +REMOTE_DATA
    >>> eve = sunpy.timeseries.TimeSeries("http://lasp.colorado.edu/eve/data_access/evewebdata/quicklook/L0CS/LATEST_EVE_L0CS_DIODES_1m.txt", source='EVE')  # doctest: +SKIP
    >>> eve.peek(subplots=True)  # doctest: +SKIP

    References
    ----------
    * `SDO Mission Homepage <https://sdo.gsfc.nasa.gov/>`__
    * `EVE Homepage <http://lasp.colorado.edu/home/eve/>`__
    * `Level 0CS Definition <http://lasp.colorado.edu/home/eve/data/>`__
    * `EVE Data Access <http://lasp.colorado.edu/home/eve/data/data-access/>`__
    * `Instrument Paper <https://doi.org/10.1007/s11207-009-9487-6>`__
    """
    # Class attribute used to specify the source class of the TimeSeries.
    _source = 'eve'
    _url = "http://lasp.colorado.edu/home/eve/"

    @peek_show
    @deprecate_positional_args_since("4.1")
    def peek(self, *, columns=None, **kwargs):
        """
        Plots the time series in a new figure.

        .. plot::

            import sunpy.timeseries
            from sunpy.data.sample import EVE_TIMESERIES
            eve = sunpy.timeseries.TimeSeries(EVE_TIMESERIES, source='eve')
            eve.peek(subplots=True, figsize=(22,11))

        Parameters
        ----------
        columns : list[str], optional
            If provided, only plot the specified columns.
        **kwargs : `dict`
            Additional plot keyword arguments that are handed to
            :meth:`pandas.DataFrame.plot`.
        """
        # Check we have a timeseries valid for plotting
        self._validate_data_for_plotting()

        # Choose title if none was specified
        if "title" not in kwargs and columns is None:
            if len(self.to_dataframe().columns) > 1:
                kwargs['title'] = 'EVE (1 minute data)'
            else:
                if self._filename is not None:
                    base = self._filename.replace('_', ' ')
                    kwargs['title'] = os.path.splitext(base)[0]
                else:
                    kwargs['title'] = 'EVE Averages'

        if columns is None:
            axes = self.to_dataframe().plot(sharex=True, **kwargs)
        else:
            data = self.to_dataframe()[columns]
            if "title" not in kwargs and len(columns) == 1:
                kwargs['title'] = 'EVE ' + columns[0].replace('_', ' ')
            else:
                kwargs['title'] = 'EVE Averages'
            axes = data.plot(sharex=True, **kwargs)

        if "subplots" in kwargs:
            fig = axes[0].get_figure()
        else:
            fig = axes.get_figure()
        return fig

    @classmethod
    def _parse_file(cls, filepath):
        """
        Parses an EVE CSV file.
        """
        cls._filename = basename(filepath)
        with codecs.open(filepath, mode='rb', encoding='ascii') as fp:
            # Determine type of EVE CSV file and parse
            line1 = fp.readline()

        if line1.startswith("Date"):
            return cls._parse_average_csv(filepath)
        elif line1.startswith(";"):
            return cls._parse_level_0cs(filepath)

    @staticmethod
    def _parse_average_csv(filepath):
        """
        Parses an EVE Averages file.
        """
        warn_deprecated(
            "Parsing SDO/EVE level 0CS average files is deprecated, and will be removed in "
            "sunpy 6.0. Parsing this data is untested, and we cannot find a file to test it with. "
            "If you know where level 0CS 'averages' files can be found, please get in touch at "
            "https://community.openastronomy.org/c/sunpy/5."
        )
        return "", read_csv(filepath, sep=",", index_col=0, parse_dates=True)

    @staticmethod
    def _parse_level_0cs(filepath):
        """
        Parses and EVE Level 0CS file.
        """
        is_missing_data = False  # boolean to check for missing data
        missing_data_val = np.nan
        header = []
        fields = []
        with codecs.open(filepath, mode='rb', encoding='ascii') as fp:
            line = fp.readline()
            # Read header at top of file
            while line.startswith(";"):
                header.append(line)
                if '; Missing data:' in line:
                    is_missing_data = True
                    missing_data_val = line.split(':')[1].strip()

                line = fp.readline()

        meta = MetaDict()
        for hline in header:
            if hline == '; Format:\n' or hline == '; Column descriptions:\n':
                continue
            elif ('Created' in hline) or ('Source' in hline):
                meta[hline.split(':',
                                 1)[0].replace(';',
                                               ' ').strip()] = hline.split(':', 1)[1].strip()
            elif ':' in hline:
                meta[hline.split(':')[0].replace(';', ' ').strip()] = hline.split(':')[1].strip()

        fieldnames_start = False
        for hline in header:
            if hline.startswith("; Format:"):
                fieldnames_start = False
            if fieldnames_start:
                fields.append(hline.split(":")[0].replace(';', ' ').strip())
            if hline.startswith("; Column descriptions:"):
                fieldnames_start = True

        # Next line is YYYY DOY MM DD
        date_parts = line.split(" ")
        year = int(date_parts[0])
        month = int(date_parts[2])
        day = int(date_parts[3])

        data = read_csv(filepath, delim_whitespace=True, names=fields, comment=';',
                        dtype={'HHMM': int})
        # First line is YYYY DOY MM DD
        data = data.iloc[1:, :]
        data['Hour'] = data['HHMM'] // 100
        data['Minute'] = data['HHMM'] % 100
        data = data.drop(['HHMM'], axis=1)

        data['Year'] = year
        data['Month'] = month
        data['Day'] = day

        datecols = ['Year', 'Month', 'Day', 'Hour', 'Minute']
        data['Time'] = to_datetime(data[datecols])
        data = data.set_index('Time')
        data = data.drop(datecols, axis=1)

        if is_missing_data:  # If missing data specified in header
            data[data == float(missing_data_val)] = np.nan

        # Add the units data
        units = OrderedDict([('XRS-B proxy', u.W/u.m**2),
                             ('XRS-A proxy', u.W/u.m**2),
                             ('SEM proxy', u.W/u.m**2),
                             ('0.1-7ESPquad', u.W/u.m**2),
                             ('17.1ESP', u.W/u.m**2),
                             ('25.7ESP', u.W/u.m**2),
                             ('30.4ESP', u.W/u.m**2),
                             ('36.6ESP', u.W/u.m**2),
                             ('darkESP', u.ct),
                             ('121.6MEGS-P', u.W/u.m**2),
                             ('darkMEGS-P', u.ct),
                             ('q0ESP', u.dimensionless_unscaled),
                             ('q1ESP', u.dimensionless_unscaled),
                             ('q2ESP', u.dimensionless_unscaled),
                             ('q3ESP', u.dimensionless_unscaled),
                             ('CMLat', u.deg),
                             ('CMLon', u.deg)])
        # Todo: check units used.
        return data, meta, units

    @classmethod
    def is_datasource_for(cls, **kwargs):
        """
        Determines if header corresponds to an EVE image.
        """
        if kwargs.get('source', ''):
            return kwargs.get('source', '').lower().startswith(cls._source)


class EVEL3TimeSeries(GenericTimeSeries):
    """    
    SDO EVE Level 3 Merged data. 

    The Extreme-ultraviolet Variability Experiment (EVE) on board SDO.
    The Level 3 Merged data product is a mission-length daily averaged, merged spectrum 
    with extracted lines, bands, photometer data. The full resolution data are at 0.02nm
    resolution, but the data are also resampled and two additional merged files are available
    at 1-nm resolution (with 0.5-nm bin centers) and 1-angstrom resolution (with 0.5-angstrom
    bin centers).

    This reader works for the spectrum. The lines, bands, and photometer data are ignored. 
    
    TODO finish docstring
    """

    _source = 'l3_eve'
    _url = "http://lasp.colorado.edu/home/eve/"


    def plot(self, axes=None, columns=None, **kwargs):
        """
        Plots the EVE Level 3 Spectrum timeseries data.

        Parameters
        ----------
        axes : numpy.ndarray of `matplotlib.axes.Axes`, optional
            The axes on which to plot the TimeSeries.
        columns : list[str], optional
            If provided, only plot the specified columns.
        **kwargs : `dict`
            Additional plot keyword arguments that are handed to `pandas.DataFrame.plot`.

        Returns
        -------
        array of `~matplotlib.axes.Axes`
            The plot axes.
        """
        axes, columns = self._setup_axes_columns(axes, columns, subplots=True)
        column_names = {"QD": "Flux \n 0.1-7nm", "CH_18": "Flux \n 18nm",
                        "CH_26": "Flux \n 26nm", "CH_30": "Flux \n 30nm", "CH_36": "Flux \n 36nm"}

        for i, name in enumerate(self.to_dataframe()[columns]):
            axes[i].plot(self._data[name],
                         label=name)
            axes[i].set_ylabel(column_names[name])
            axes[i].legend(loc="upper right")
        axes[-1].set_xlim(self._data.index[0], self._data.index[-1])
        self._setup_x_axis(axes)
        return axes

    @peek_show
    @deprecate_positional_args_since("4.1")
    def peek(self, *, title="EVE/ESP Level 1", columns=None, **kwargs):
        """
        Displays the EVE ESP Level 1 timeseries data by calling
        `~sunpy.timeseries.sources.eve.ESPTimeSeries.plot`.

        Parameters
        ----------
        title : `str`, optional
            The title of the plot. Defaults to "EVE/ESP Level 1".
        columns : list[str], optional
            If provided, only plot the specified columns.
        **kwargs : `dict`
            Additional plot keyword arguments that are handed to `pandas.DataFrame.plot`.
        """
        axes = self.plot(columns=columns, **kwargs)
        axes[0].set_title(title)
        fig = axes[0].get_figure()
        fig.tight_layout()
        fig.subplots_adjust(hspace=0.05)
        return fig


    @classmethod
    def _parse_file(cls, filepath):
        """
        Parses EVE Level 3 data file.
        """
        hdus = sunpy.io.read_file(filepath)
        return cls._parse_hdus(hdus)


    @classmethod
    def _parse_hdus(cls, hdulist):
        """
        Parses the header data units from an EVE Level 3 merged data file.
        """
        # EVE level 3 merged data   
        # the names of the HDUs (the first HDU is a dummy header 
        # added by the FITS writer and can be discarded)
        hdu_names = [x.header['extname'] if 'extname' in x.header.keys() else '' for x in hdulist]

        # the merged file has
        
        # the main header info is in the MergedData header
        # as is the spectral irradiance & YYYYDOY date
        md_idx = hdu_names.index('MergedData')                          # get the index of the MergedData HDU
        header = MetaDict(OrderedDict(hdulist[md_idx].header))
        irradiance = hdulist[md_idx].data['SP_IRRADIANCE']              # 2D array of yyyydoy x wavelength bins
        yds = hdulist[md_idx].data['YYYYDOY']
           
        # wavelength is in the SpectrumMeta HDU
        sm_idx = hdu_names.index('SpectrumMeta')                        # index of the SpectrumMeta HDU
        wavelengths = hdulist[sm_idx].data['WAVELENGTH'].reshape(-1)    # 1D array of the wavelength bins
        colnames = [f'{i}nm' for i in wavelengths]

        # build Time object from year-doy for dataframe index
        years = yds // 1000                                             # extract year & doy to build Time object
        doys = yds - (years * 1000)
        times_df = DataFrame({'yyyy': years, 'doy': doys})
        times = times_df.apply(lambda x: Time(f"{x.yyyy:>04d}:{x.doy:>03d}", format='yday'), axis=1)
        times = times.apply(lambda x: x.isot)                           # use isot format
        
        # dataframe has 1 columns for each wavelength bin
        data = DataFrame(irradiance, index=times.astype('datetime64'), columns=colnames)

        # irradiance units is W/m^2/nm
        units = OrderedDict([(i, u.W/u.m**2/u.nm) for i in colnames])

        return data, header, units
                      

    @classmethod
    def is_datasource_for(cls, **kwargs):
        """
        Determines if header corresponds to an EVE image.
        """
        if kwargs.get('source', ''):
            return kwargs.get('source', '').lower().startswith(cls._source)
        if 'meta' in kwargs.keys():
            # Level 2/2B data products also have 'EVE_MEGS' in the 'INSTRUME' field
            # so need to check the filename to make sure this is a L3 merged file
            return (kwargs['meta'].get('TELESCOP', '').endswith('SDO/EVE')) & \
                   (kwargs['meta'].get('INSTRUME', '').endswith('EVE_MEGS')) & \
                   (kwargs['meta'].get('FILENAME', '').startswith('EVE_L3'))
