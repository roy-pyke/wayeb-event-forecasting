from datetime import timedelta
import pytest
from acnresearch.requests import request_asof, timestamp, recording_filename


def test_no_future_request_or_endpoint_fallback():
    t = timestamp('2020-01-01T00:00:00+00:00')
    s = {'kWhDelivered': 8, 'disconnectTime': '2020-01-01T08:00:00+00:00', 'userInputs': []}
    assert request_asof(s, t) is None
    s['userInputs'] = [{'kWhRequested': 18, 'requestedDeparture': '2020-01-01T07:00:00+00:00', 'modifiedAt': '2020-01-01T00:10:00+00:00'}]
    assert request_asof(s, t) is None
    assert request_asof(s, t + timedelta(minutes=10))['kwh_requested'] == 18
    s['userInputs'].append({'kWhRequested': 30, 'requestedDeparture': '2020-01-01T09:00:00+00:00', 'modifiedAt': '2020-01-01T00:30:00+00:00'})
    assert request_asof(s, t + timedelta(minutes=10))['kwh_requested'] == 18


def test_timestamp_and_conflict_contract():
    with pytest.raises(ValueError): timestamp('2020-01-01T00:00:00')
    entries = [{'kWhRequested': e, 'requestedDeparture': '2020-01-01T07:00:00+00:00', 'modifiedAt': '2020-01-01T00:00:00+00:00'} for e in [8, 18]]
    with pytest.raises(ValueError): request_asof({'userInputs': entries}, '2020-01-01T00:01:00+00:00')


def test_session_filename_mapping():
    assert recording_filename('2_39_131_30_2020-05-11 01:36:18.763379') == '2-39-131-30-2020-05-11T01-36-18-763379.csv.gz'
