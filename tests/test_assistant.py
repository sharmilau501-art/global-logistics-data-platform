"""Deterministic assistant behavior without any external libraries or cloud calls."""
from unittest.mock import patch
import json
import pytest

from logistics.assistant import (QUESTIONS, classify_question, explain,
                                 local_ollama_explanation)


@pytest.fixture
def snapshot():
    return {
        'overview': {'shipments': 10, 'delivered': 8, 'late': 2,
                     'customs_holds': 3, 'on_time_pct': 75.0},
        'carriers': [
            {'carrier': 'CARRIER_B', 'shipments': 3, 'late': 2},
            {'carrier': 'CARRIER_A', 'shipments': 7, 'late': 0},
        ],
        'routes': [
            {'route': 'Shanghai, China → Los Angeles, United States',
             'shipments': 6, 'late': 2},
            {'route': 'Mumbai, India → New York, United States',
             'shipments': 4, 'late': 0},
        ],
        'delay_reasons': [{'delay_reason': 'WEATHER', 'affected_shipments': 2},
                          {'delay_reason': 'PORT_CONGESTION', 'affected_shipments': 1}],
    }


@pytest.mark.parametrize('question,intent', [
    ('Which carrier has the most late deliveries?', 'carrier'),
    ('Which route has the most delays?', 'route'),
    ('Why are there delays?', 'reasons'),
    ('How many customs holds?', 'customs'),
    ('How many shipments were delivered?', 'overview'),
    ('DELETE FROM fact_shipment', 'unsupported'),
    ('', 'unsupported'),
])
def test_intent(question, intent):
    assert classify_question(question) == intent


def test_overview_is_grounded(snapshot):
    answer = explain('How many shipments?', snapshot)
    assert '10 shipments' in answer['answer']
    assert '75.00%' in answer['answer']
    assert answer['evidence']['overview']['delivered'] == 8


def test_carrier_count_vs_rate(snapshot):
    result = explain('Most delayed carrier?', snapshot)
    assert 'CARRIER_B' in result['answer']
    assert 'not adjusted' in result['answer']


def test_route_ranking(snapshot):
    result = explain('Which route has most late deliveries?', snapshot)
    assert 'Shanghai' in result['answer']
    assert result['evidence']['top_routes'][0]['late'] == 2


def test_reasons_are_not_causal_claims(snapshot):
    result = explain('Why are shipments delayed?', snapshot)
    assert 'WEATHER: 2' in result['answer']
    assert 'not proven causal' in result['answer']


def test_customs(snapshot):
    assert '3 of 10' in explain('Customs holds?', snapshot)['answer']


def test_unsupported_does_not_execute_sql(snapshot):
    result = explain('DROP TABLE fact_shipment;', snapshot)
    assert result['intent'] == 'unsupported'
    assert result['evidence'] == {}


def test_empty_selection(snapshot):
    snapshot['carriers'] = []
    snapshot['routes'] = []
    snapshot['overview'] = {'shipments': 0, 'delivered': 0, 'late': 0,
                            'customs_holds': 0, 'on_time_pct': None}
    assert 'No carrier' in explain('Which carrier?', snapshot)['answer']
    assert 'No routes' in explain('Which route?', snapshot)['answer']
    assert 'not available' in explain('How many shipments?', snapshot)['answer']


def test_ollama_does_not_run_on_unsupported_intent(snapshot):
    with pytest.raises(ValueError, match='supported'):
        local_ollama_explanation('delete database', explain('delete database', snapshot))


def test_ollama_endpoint_is_localhost_only(snapshot):
    result = explain('How many shipments?', snapshot)
    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, max_size): return json.dumps({'response': 'Synthetic summary.'}).encode()
    def capture(req, timeout):
        assert req.full_url == 'http://127.0.0.1:11434/api/generate'
        payload = json.loads(req.data)
        assert payload['stream'] is False
        assert payload['model'] == 'local-test'
        assert '10 shipments' in payload['prompt']
        return FakeResponse()
    with patch('logistics.assistant.urlopen', side_effect=capture):
        assert local_ollama_explanation('How many shipments?', result, 'local-test') == 'Synthetic summary.'


def test_example_questions_list():
    assert len(QUESTIONS) >= 4
