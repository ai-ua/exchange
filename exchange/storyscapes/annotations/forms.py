# -*- coding: utf-8 -*-
from django import forms
from exchange.storyscapes.models.marker import Marker
from exchange.storyscapes.utils import (
    datetime_to_seconds, make_point, parse_date_time)

import json


class MarkerForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        self.form_mode = kwargs.pop('form_mode', 'client')
        super(MarkerForm, self).__init__(*args, **kwargs)

    def parse_float(self, name):
        val = self.data.get(name, None)
        if not val:
            return None
        try:
            return float(val)
        except ValueError:
            self._my_errors[name] = 'Invalid value for %s : "%s"' % (name, val)

    def full_clean(self):
        self._my_errors = {}
        geom = self.data.get('geometry', None)
        if geom:
            if isinstance(geom, basestring):  # noqa
                try:
                    json.loads(geom)
                except ValueError:
                    self._my_errors['geometry'] = 'Invalid JSON'
            elif isinstance(geom, dict):
                geom = json.dumps(geom)
            else:
                self._my_errors[
                    'geometry'] = 'geometry should be string or dict'
            self.data['the_geom'] = geom
        lat, lon = self.parse_float('lat'), self.parse_float('lon')
        if all([lat, lon]):
            self.data['the_geom'] = make_point(lon, lat)
        self._convert_time('start_time')
        self._convert_time('end_time')
        super(MarkerForm, self).full_clean()
        self._errors.update(self._my_errors)

    def _convert_time(self, key):
        val = self.data.get(key, None)
        if not val:
            return
        numeric = None
        # the client will send things back as ints
        if self.form_mode == 'client':
            try:
                numeric = int(val)
            except ValueError:
                pass
        # otherwise, parse as formatted strings
        if not numeric:
            err = None
            parsed = None
            try:
                parsed = parse_date_time(val)
            except ValueError as e:
                err = str(e)
            if val is not None and parsed is None:
                err = ('Unable to read as date : {0}, please format '
                       'as yyyy-mm-dd').format(val)
            if err:
                self._my_errors[key] = err
            if parsed:
                numeric = int(datetime_to_seconds(parsed))
        self.data[key] = str(numeric) if numeric is not None else None

    class Meta:
        model = Marker
        fields = '__all__'
