"""
Tests for monitoring custom metrics.
"""
from django.test import TestCase
from edx_django_utils import monitoring
from edx_django_utils.monitoring.middleware import MonitoringCustomMetrics
from mock import call, patch


class TestMonitoringCustomMetrics(TestCase):
    """
    Test the monitoring_utils middleware and helpers
    """

    @patch('newrelic.agent')
    def test_custom_metrics_with_new_relic(self, mock_newrelic_agent):
        """
        Test normal usage of collecting custom metrics and reporting to New Relic
        """
        monitoring.accumulate('hello', 10)
        monitoring.accumulate('world', 10)
        monitoring.accumulate('world', 10)
        monitoring.increment('foo')
        monitoring.increment('foo')

        # based on the metric data above, we expect the following calls to newrelic:
        nr_agent_calls_expected = [
            call('hello', 10),
            call('world', 20),
            call('foo', 2),
        ]

        # fake a response to trigger metrics reporting
        MonitoringCustomMetrics().process_response(
            'fake request',
            'fake response',
        )

        # Assert call counts to newrelic.agent.add_custom_parameter()
        expected_call_count = len(nr_agent_calls_expected)
        measured_call_count = mock_newrelic_agent.add_custom_parameter.call_count
        self.assertEqual(expected_call_count, measured_call_count)

        # Assert call args to newrelic.agent.add_custom_parameter().  Due to
        # the nature of python dicts, call order is undefined.
        mock_newrelic_agent.add_custom_parameter.has_calls(nr_agent_calls_expected, any_order=True)