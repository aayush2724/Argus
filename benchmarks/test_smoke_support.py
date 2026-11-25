import http.client
import json
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from fixture_analyzer import Handler, ThreadingHTTPServer
from smoke_support import audit_results, clean_environment, run_id


class SmokeSupportTests(unittest.TestCase):
    def test_environment_does_not_copy_credentials_or_docker_configuration(self):
        secrets = {name: "fake-secret" for name in (
            "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GCP_CREDENTIALS_PATH",
            "GOOGLE_APPLICATION_CREDENTIALS", "DOCKER_HOST", "DOCKER_CONTEXT", "AWS_SECRET_ACCESS_KEY")}
        with patch.dict(os.environ, secrets):
            env = clean_environment(Path('/tmp/private-home'), Path('/tmp/private-tmp'), '/usr/bin:/bin')
        self.assertFalse(set(env) & set(secrets))
        self.assertNotIn("fake-secret", env.values())
        with self.assertRaises(ValueError):
            clean_environment(Path('relative'), Path('/tmp/x'), '/bin')

    def test_ids_are_unique(self):
        self.assertNotEqual(run_id(), run_id())

    def test_audit_keeps_all_findings_in_denominator(self):
        findings = [{"finding_id": str(i), "ground_truth": "true_positive"} for i in range(5)]
        results = [
            {"finding_id": "0", "status": "success", "prediction": "true_positive", "ground_truth": "true_positive"},
            {"finding_id": "1", "status": "success", "prediction": "invalid", "ground_truth": "true_positive"},
            {"finding_id": "2", "status": "success", "ground_truth": "true_positive"},
            {"finding_id": "3", "status": "error"},
            {"status": "error"},
        ]
        audit = audit_results(findings, results)
        self.assertEqual((audit['input_count'], audit['eligible'], audit['invalid_prediction'],
                          audit['process_error'], audit['missing_result'], audit['unassigned_error_rows']),
                         (5, 1, 2, 1, 1, 1))
        self.assertEqual(audit['confusion']['true_positive:true_positive'], 1)
        with self.assertRaises(ValueError):
            audit_results(findings, results + [results[0]])

    def test_label_mismatch_is_ineligible(self):
        audit = audit_results([{'finding_id': 'a', 'ground_truth': 'true_positive'}],
                              [{'finding_id': 'a', 'status': 'success', 'prediction': 'true_positive',
                                'ground_truth': 'false_positive'}])
        self.assertEqual(audit['label_mismatch'], 1)


class FixtureHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, method, path, body=None, timeout=2):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=timeout)
        try:
            conn.request(method, path, json.dumps(body) if body is not None else None)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def test_contract_and_partial_failures(self):
        self.assertEqual(self.request('GET', '/health')[0], 200)
        self.assertEqual(self.request('POST', '/preprocess', {})[1]['status'], 'success')
        for mode in ('true_positive', 'false_positive', 'invalid'):
            self.assertEqual(self.request('POST', '/analyze', {'finding_data': {'mode': mode}})[1]['prediction'], mode)
        self.assertNotIn('prediction', self.request('POST', '/analyze', {'finding_data': {'mode': 'missing'}})[1])
        self.assertEqual(self.request('POST', '/analyze', {'finding_data': {'mode': 'error'}})[0], 500)
        self.assertEqual(self.request('POST', '/analyze', {})[0], 400)
        with self.assertRaises(TimeoutError):
            self.request('POST', '/analyze', {'finding_data': {'mode': 'timeout'}}, timeout=0.05)


if __name__ == '__main__':
    unittest.main()
