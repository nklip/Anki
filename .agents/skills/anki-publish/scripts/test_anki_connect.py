"""Offline safety checks; no running Anki instance is contacted."""
import copy
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import urllib.request

import anki_connect as ac


class FakeClient:
    def __init__(self):
        self.profile = 'Test'
        self.note = {'noteId': 7, 'modelName': 'Basic Publisher', 'tags': ['owned', 'manual'],
                     'fields': {'Front': {'value': 'Question', 'order': 0},
                                'Back': {'value': 'Old answer', 'order': 1}}, 'cards': [11]}
        self.names = ['Front', 'Back']
        self.templates = {'Card 1': {'Front': '{{Front}}', 'Back': '{{FrontSide}}<hr>{{Back}}'}}
        self.styling = {'css': '.card { color: black; }'}
        self.cards = [{'cardId': 11, 'note': 7, 'ord': 0, 'due': 99, 'queue': -1, 'type': 2,
                       'interval': 30, 'factor': 2500, 'reps': 8, 'lapses': 1, 'left': 0,
                       'flags': 3, 'deckName': 'Study', 'modelName': 'Basic Publisher',
                       'answer': 'Old answer', 'question': 'Question', 'fields': {},
                       'css': 'old', 'mod': 100, 'futureProperty': {'preserve': True}}]
        self.reviews = {'11': [{'id': 123, 'ease': 3, 'ivl': 30, 'time': 900}]}
        self.writes = []
        self.calls = []
        self.on_write = None

    def call(self, action, **params):
        self.calls.append(action)
        values = {'getActiveProfile': self.profile, 'notesInfo': [self.note],
                  'modelFieldNames': self.names, 'modelTemplates': self.templates,
                  'modelStyling': self.styling, 'cardsInfo': self.cards,
                  'getReviewsOfCards': self.reviews}
        if action in values:
            return copy.deepcopy(values[action])
        self.writes.append((action, copy.deepcopy(params)))
        if action == 'updateNoteFields':
            for key, value in params['note']['fields'].items():
                self.note['fields'][key]['value'] = value
            self.cards[0].update(answer='Rendered new answer', mod=101)
        if self.on_write:
            self.on_write(self)
        return None


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name) / 'snapshot.json'
        self.client = FakeClient()
        self.expected = ac.snapshot(self.client, 7)
        ac.save(self.base, self.expected)

    def update(self, fields=None):
        return ac.update_note(self.client, 7, fields or {'Back': 'New answer'}, self.expected, self.base)

    def assert_no_write(self):
        self.assertEqual(self.client.writes, [])
        self.assertEqual(list(self.base.parent.glob('*.prewrite.json')), [])

    def test_preserves_all_returned_state_and_saves_checkpoints(self):
        result = self.update()
        self.assertEqual(result['status'], 'updated')
        self.assertIn('futureProperty', result['verified']['card_properties'])
        self.assertIn('Unexposed FSRS', result['limitations'])
        before, after = ac.json_object(result['before']), ac.json_object(result['after'])
        self.assertEqual(before, self.expected)
        self.assertEqual(after['note']['tags'], ['manual', 'owned'])
        self.assertEqual(after['cards'][0]['queue'], -1)
        self.assertEqual(after['cards'][0]['flags'], 3)
        self.assertEqual(after['reviews'], before['reviews'])
        self.assertEqual(len(self.client.writes), 1)

    def test_second_run_is_noop(self):
        self.update()
        self.expected = ac.snapshot(self.client, 7)
        result = self.update()
        self.assertEqual(result['status'], 'no-op')
        self.assertEqual(len(self.client.writes), 1)

    def test_native_framing_publication_is_field_only_and_idempotent(self):
        # Keep Basic's normal FrontSide/divider and publish only the answer body.
        self.client.templates['Card 1']['Back'] = (
            '{{FrontSide}}<hr id="answer"><div class="back-left">{{Back}}</div>')
        self.expected = ac.snapshot(self.client, 7)
        fields = {
            'Front': 'Article title',
            'Back': '<div class="anki-publish-test-back" style="padding:0;margin:0">'
                    '<p>Article body</p><img src="verified.svg"><h1>Sources</h1></div>',
        }
        result = self.update(fields)
        before, after = ac.json_object(result['before']), ac.json_object(result['after'])
        self.assertEqual(self.client.writes, [('updateNoteFields', {'note': {'id': 7, 'fields': fields}})])
        self.assertEqual(before['model'], after['model'])
        self.assertEqual(before['reviews'], after['reviews'])
        self.assertTrue(result['verified']['all_returned_card_properties_unchanged'])
        self.expected = ac.snapshot(self.client, 7)
        self.assertEqual(self.update(fields)['status'], 'no-op')
        self.assertEqual(len(self.client.writes), 1)

    def test_inherited_text_update_preserves_front_shared_size_and_review_state(self):
        self.client.styling = {'css': '.card { font-size: 20px; }'}
        self.expected = ac.snapshot(self.client, 7)
        back = ('<div style="font-size:inherit;line-height:1.6">'
                '<h2 style="font-size:1.5em;line-height:1.25">Heading</h2>'
                '<p style="font-size:inherit">Body</p></div>')
        result = self.update({'Back': back})
        before, after = ac.json_object(result['before']), ac.json_object(result['after'])
        self.assertEqual(after['note']['fields']['Front'], before['note']['fields']['Front'])
        self.assertEqual(after['model'], before['model'])
        self.assertEqual(after['reviews'], before['reviews'])
        self.assertTrue(result['verified']['all_returned_card_properties_unchanged'])
        self.assertEqual(self.client.writes, [('updateNoteFields', {'note': {'id': 7, 'fields': {'Back': back}}})])

    def test_stale_content_tags_profile_and_review_state_are_rejected(self):
        changes = [lambda c: c.note['fields']['Back'].update(value='Manual edit'),
                   lambda c: c.note['tags'].append('new-manual-tag'),
                   lambda c: setattr(c, 'profile', 'Other'),
                   lambda c: c.cards[0].update(due=100),
                   lambda c: c.reviews['11'].append({'id': 124})]
        for change in changes:
            with self.subTest(change=change):
                self.client = FakeClient()
                change(self.client)
                with self.assertRaisesRegex(ac.PublishError, 'Stale snapshot'):
                    self.update()
                self.assert_no_write()

    def test_unknown_and_blank_fields_are_rejected(self):
        for fields in ({'Typo': 'x'}, {'Back': ''}, {'Back': '  '}, {'Back': '<br>'},
                       {'Back': '<div>&nbsp;</div>'}, {'Back': '<!--comment-->'},
                       {'Back': '<script>hidden</script>'}, {'Back': None}):
            with self.subTest(fields=fields):
                with self.assertRaises(ac.PublishError):
                    self.update(fields)
                self.assert_no_write()

    def test_media_only_field_is_supported(self):
        self.assertEqual(self.update({'Back': '<img src="image.png">'})['status'], 'updated')

    def test_cloze_and_conditionals_rejected_on_either_side(self):
        for side in ('Front', 'Back'):
            for template in ('{{cloze:Front}}', '{{#Front}}{{Front}}{{/Front}}',
                             '{{^Back}}Missing{{/Back}}', '{{type:Back}}'):
                with self.subTest(side=side, template=template):
                    self.client = FakeClient()
                    self.client.templates['Card 1'][side] = template
                    self.expected = ac.snapshot(self.client, 7)
                    with self.assertRaises(ac.PublishError):
                        self.update()
                    self.assert_no_write()

    def test_missing_card_property_blocks_update(self):
        for property_name in ('due', 'left', 'deckName'):
            with self.subTest(property_name=property_name):
                self.client = FakeClient()
                del self.client.cards[0][property_name]
                self.expected = ac.snapshot(self.client, 7)
                with self.assertRaisesRegex(ac.PublishError, 'required card properties: ' + property_name):
                    self.update()
                self.assert_no_write()

    def test_source_id_is_immutable(self):
        self.client.names.append('SourceId')
        self.client.note['fields']['SourceId'] = {'value': 'stable-source', 'order': 2}
        self.expected = ac.snapshot(self.client, 7)
        with self.assertRaisesRegex(ac.PublishError, 'SourceId is immutable'):
            self.update({'SourceId': 'renamed-source'})
        self.assert_no_write()
        self.assertEqual(self.update({'SourceId': 'stable-source'})['status'], 'no-op')

    def test_missing_reverse_card_cannot_be_created_by_filling_back(self):
        self.client.templates['Card 2'] = {'Front': '{{Back}}', 'Back': '{{Front}}'}
        self.client.note['fields']['Back']['value'] = ''
        self.expected = ac.snapshot(self.client, 7)
        with self.assertRaisesRegex(ac.PublishError, 'exactly every template ordinal'):
            self.update()
        self.assert_no_write()

    def test_blank_referenced_field_rejected_even_with_all_existing_cards(self):
        self.client.note['fields']['Back']['value'] = '<br>'
        self.expected = ac.snapshot(self.client, 7)
        with self.assertRaisesRegex(ac.PublishError, 'previously blank template-referenced'):
            self.update()
        self.assert_no_write()

    def test_script_templates_rejected_before_requesting_rendered_cards(self):
        for side in ('Front', 'Back'):
            with self.subTest(side=side):
                self.client = FakeClient()
                self.client.templates['Card 1'][side] += '<SCRIPT>changeState()</SCRIPT>'
                with self.assertRaisesRegex(ac.PublishError, 'Scripted templates'):
                    ac.snapshot(self.client, 7)
                self.assertNotIn('cardsInfo', self.client.calls)
                self.assert_no_write()

    def test_snapshots_and_checkpoints_are_private_even_with_open_umask(self):
        previous = os.umask(0)
        try:
            ac.save(self.base, self.expected)
            result = self.update()
        finally:
            os.umask(previous)
        for path in (self.base, result['before'], result['after']):
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)

    def test_malformed_note_data_fails_with_clear_diagnostics(self):
        cases = [('tags', None), ('tags', [12]), ('cards', [['nested']]),
                 ('fields', {'Front': {'value': None, 'order': 0}}), ('modelName', '')]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                self.client = FakeClient()
                self.client.note[key] = value
                with self.assertRaises(ac.PublishError):
                    ac.snapshot(self.client, 7)
                self.assert_no_write()

    def test_missing_model_field_blocks_update(self):
        self.client.names.append('Missing')
        self.expected = ac.snapshot(self.client, 7)
        with self.assertRaisesRegex(ac.PublishError, 'every model field'):
            self.update()
        self.assert_no_write()

    def test_changed_schedule_reviews_template_and_unknown_state_fail_verification(self):
        changes = [lambda c: c.cards[0].update(due=100),
                   lambda c: c.cards[0].update(queue=2),
                   lambda c: c.cards[0].update(futureProperty={'preserve': False}),
                   lambda c: c.reviews['11'].append({'id': 124}),
                   lambda c: c.templates['Card 1'].update(Back='Changed'),
                   lambda c: c.note['tags'].append('unintended')]
        for change in changes:
            with self.subTest(change=change):
                self.client = FakeClient()
                self.expected = ac.snapshot(self.client, 7)
                self.client.on_write = change
                with self.assertRaisesRegex(ac.PublishError, 'preservation mismatch'):
                    self.update()
                self.assertEqual(len(self.client.writes), 1)
        self.assertEqual(len(list(self.base.parent.glob('*.after.json'))), len(changes))

    def test_topology_change_keeps_failure_checkpoint(self):
        def alter_cards(client):
            client.note['cards'] = [12]
            client.cards[0]['cardId'] = 12
            client.reviews = {'12': []}
        self.client.on_write = alter_cards
        with self.assertRaisesRegex(ac.PublishError, 'preservation mismatch'):
            self.update()
        after = ac.json_object(next(self.base.parent.glob('*.after.json')))
        self.assertEqual(after['note']['cards'], [12])
        self.assertEqual(len(self.client.writes), 1)

    def test_uncertain_mutation_is_not_retried_even_when_change_applied(self):
        def timeout(client):
            raise ac.PublishError('Timeout after server applied update')
        self.client.on_write = timeout
        with self.assertRaisesRegex(ac.PublishError, 'no retry or rollback'):
            self.update()
        after = ac.json_object(next(self.base.parent.glob('*.after.json')))
        self.assertEqual(after['note']['fields']['Back']['value'], 'New answer')
        self.assertEqual(len(self.client.writes), 1)

    def test_failed_post_snapshot_is_recorded(self):
        self.client.on_write = lambda c: setattr(c, 'reviews', {})
        with self.assertRaisesRegex(ac.PublishError, 'Outcome uncertain'):
            self.update()
        after = ac.json_object(next(self.base.parent.glob('*.after.json')))
        self.assertIn('snapshot_error', after)
        self.assertEqual(len(self.client.writes), 1)

    def test_readonly_verify_recovers_applied_update_with_lost_response(self):
        def lose_response(client):
            raise ac.PublishError('Connection lost after update')
        self.client.on_write = lose_response
        with self.assertRaisesRegex(ac.PublishError, 'no retry or rollback'):
            self.update()
        original = next(self.base.parent.glob('*.prewrite.json'))
        result = ac.verify_note(self.client, 7, {'Back': 'New answer'}, ac.json_object(original), original)
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['verified'], ac.coverage(self.expected)['verified'])
        self.assertIn('Unexposed FSRS', result['limitations'])
        self.assertEqual(ac.json_object(result['after'])['note']['fields']['Back']['value'], 'New answer')
        self.assertEqual(stat.S_IMODE(os.stat(result['after']).st_mode), 0o600)
        self.assertEqual(len(self.client.writes), 1)

    def test_readonly_verify_catches_schedule_change_against_original_baseline(self):
        self.client.note['fields']['Back']['value'] = 'New answer'
        self.client.cards[0]['due'] += 1
        with self.assertRaisesRegex(ac.PublishError, 'Verification mismatch against original'):
            ac.verify_note(self.client, 7, {'Back': 'New answer'}, self.expected, self.base)
        after = ac.json_object(next(self.base.parent.glob('*.verification.json')))
        self.assertEqual(after['cards'][0]['due'], 100)
        self.assertEqual(self.client.writes, [])

    def test_readonly_verify_rejects_wrong_note_without_requests(self):
        self.client.calls.clear()
        with self.assertRaisesRegex(ac.PublishError, 'checkpoint note ID differs'):
            ac.verify_note(self.client, 8, {'Back': 'New answer'}, self.expected, self.base)
        self.assertEqual(self.client.calls, [])
        self.assert_no_write()

    def test_verify_cli_uses_original_checkpoint_without_mutation(self):
        fields_path = self.base.parent / 'fields.json'
        ac.save(fields_path, {'Back': 'New answer'})
        self.client.note['fields']['Back']['value'] = 'New answer'
        output = io.StringIO()
        with patch.object(ac, 'Client', return_value=self.client), patch('sys.stdout', output):
            status = ac.main(['verify', '7', '--fields', str(fields_path), '--before', str(self.base)])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue())['status'], 'verified')
        self.assertEqual(self.client.writes, [])


class TransportAndWriteTests(unittest.TestCase):
    def test_only_numeric_loopback_plain_http_allowed(self):
        for url in ('https://127.0.0.1:8765', 'http://example.com:8765',
                    'http://192.168.0.1:8765', 'http://localhost:8765',
                    'http://user:password@127.0.0.1:8765', 'http://127.0.0.1:8765/?q=x'):
            with self.subTest(url=url), self.assertRaises(ac.PublishError):
                ac.Client(url)
        ac.Client('http://[::1]:8765')

    def test_timeout_does_not_retry(self):
        client = ac.Client()
        with patch.object(client.opener, 'open', side_effect=TimeoutError) as opened:
            with self.assertRaisesRegex(ac.PublishError, 'No retry'):
                client.call('addNote', note={})
            self.assertEqual(opened.call_count, 1)

    def test_api_version_and_environment_key(self):
        client = ac.Client()
        response = io.BytesIO(b'{"result": 6, "error": null}')
        with patch.dict('os.environ', {'ANKI_CONNECT_KEY': 'test-secret'}), \
                patch.object(client.opener, 'open', return_value=response) as opened:
            self.assertEqual(client.call('version'), 6)
            payload = json.loads(opened.call_args.args[0].data)
            self.assertEqual(payload, {'action': 'version', 'version': 6, 'params': {}, 'key': 'test-secret'})

    def test_redirects_forbidden(self):
        with self.assertRaises(ac.PublishError):
            ac.NoRedirect().redirect_request(None, None, 302, '', {}, 'http://remote.example')

    def test_generic_writer_has_small_allowlist(self):
        client = FakeClient()
        for action in ('deleteNotes', 'updateNoteFields', 'changeDeck', 'setDueDate'):
            with self.subTest(action=action), self.assertRaises(ac.PublishError):
                ac.generic_write(client, action, {})
        self.assertEqual(client.writes, [])

    def test_add_note_requires_no_duplicates_and_source_identity(self):
        client = FakeClient()
        bad = [{}, {'note': {'options': {'allowDuplicate': True}, 'fields': {'SourceId': 'abc'}}},
               {'note': {'options': {'allowDuplicate': False}, 'fields': {'Front': 'Question'}}}]
        for params in bad:
            with self.subTest(params=params), self.assertRaises(ac.PublishError):
                ac.generic_write(client, 'addNote', params)
        self.assertEqual(client.writes, [])
        for identity in ({'fields': {'SourceId': 'abc'}}, {'tags': ['anki-publish::source::abc']}):
            ac.generic_write(client, 'addNote', {'note': {'options': {'allowDuplicate': False}, **identity}})
        self.assertEqual(len(client.writes), 2)


if __name__ == '__main__':
    unittest.main()
