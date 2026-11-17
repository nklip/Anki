#!/usr/bin/env python3
"""Conservative AnkiConnect v6 access; never retries a request or repairs review state."""
import argparse
import copy
import datetime
import html
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

READ_ACTIONS = frozenset('version apiReflect getActiveProfile deckNamesAndIds modelFieldNames modelTemplates modelStyling findNotes notesInfo cardsInfo getReviewsOfCards retrieveMediaFile'.split())
WRITE_ACTIONS = frozenset('addNote createModel createDeck storeMediaFile'.split())
CARD_REQUIRED = frozenset('cardId note ord due queue type interval factor reps lapses left deckName'.split())
CARD_CONTENT = frozenset('answer question fields css mod'.split())


class PublishError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PublishError('HTTP redirects are forbidden.')


class Client:
    def __init__(self, url=None, timeout=10):
        self.url = url or os.environ.get('ANKI_CONNECT_URL', 'http://127.0.0.1:8765')
        parsed = urllib.parse.urlsplit(self.url)
        try:
            loopback = ipaddress.ip_address(parsed.hostname or '').is_loopback
            port = parsed.port
        except ValueError:
            loopback, port = False, None
        if not (parsed.scheme == 'http' and loopback and port and not parsed.username
                and not parsed.password and parsed.path in ('', '/')
                and not parsed.query and not parsed.fragment):
            raise PublishError('Use an HTTP URL with a literal loopback IP and explicit port.')
        if not 0 < timeout <= 60:
            raise PublishError('Timeout must be greater than 0 and at most 60 seconds.')
        self.timeout = timeout
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def call(self, action, **params):
        payload = {'action': action, 'version': 6, 'params': params}
        if os.environ.get('ANKI_CONNECT_KEY'):
            payload['key'] = os.environ['ANKI_CONNECT_KEY']
        request = urllib.request.Request(self.url, json.dumps(payload).encode(),
                                         {'Content-Type': 'application/json'})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                data = json.load(response)
        except (OSError, ValueError, urllib.error.URLError) as exc:
            raise PublishError('Request failed; outcome may be uncertain. No retry was made. '
                               + type(exc).__name__) from exc
        if not isinstance(data, dict) or set(data) != {'result', 'error'}:
            raise PublishError('Invalid AnkiConnect response; no retry was made.')
        if data['error'] is not None:
            raise PublishError(f"AnkiConnect {action} failed: {data['error']}")
        return data['result']


def json_object(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise PublishError('Expected a JSON object.')
    return data


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with os.fdopen(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                       'w', encoding='utf-8') as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def snapshot(client, note_id):
    profile = client.call('getActiveProfile')
    notes = client.call('notesInfo', notes=[note_id])
    if not isinstance(profile, str) or not profile or not isinstance(notes, list) or len(notes) != 1:
        raise PublishError('Cannot identify the profile and exactly one note.')
    note = copy.deepcopy(notes[0])
    if (not isinstance(note, dict) or note.get('noteId') != note_id
            or not isinstance(note.get('fields'), dict) or not note['fields']
            or not isinstance(note.get('modelName'), str) or not note['modelName'].strip()
            or not isinstance(note.get('tags'), list)
            or any(not isinstance(tag, str) for tag in note['tags'])):
        raise PublishError('Note is missing or malformed.')
    if any(not isinstance(name, str) or not name or not isinstance(field, dict)
           or not isinstance(field.get('value'), str) or type(field.get('order')) is not int
           for name, field in note['fields'].items()):
        raise PublishError('Note fields must contain string values and integer field orders.')
    model = note['modelName']
    names = client.call('modelFieldNames', modelName=model)
    templates = client.call('modelTemplates', modelName=model)
    styling = client.call('modelStyling', modelName=model)
    if (not isinstance(names, list) or not names or any(not isinstance(n, str) or not n for n in names)
            or len(names) != len(set(names)) or not isinstance(templates, dict) or not templates
            or any(not isinstance(t, dict) or any(not isinstance(t.get(s), str) for s in ('Front', 'Back'))
                   for t in templates.values())
            or not isinstance(styling, dict) or not isinstance(styling.get('css'), str)):
        raise PublishError('Model fields, templates, or styling are malformed.')
    if any(re.search(r'<\s*script\b', t[s], re.I) for t in templates.values() for s in ('Front', 'Back')):
        raise PublishError('Scripted templates are unsupported; cardsInfo was not requested.')
    ids = note.get('cards')
    if (not isinstance(ids, list) or any(type(i) is not int or i <= 0 for i in ids)
            or len(ids) != len(set(ids))):
        raise PublishError('Invalid card identity list.')
    cards = client.call('cardsInfo', cards=ids)
    reviews = client.call('getReviewsOfCards', cards=ids)
    if (not isinstance(cards, list) or len(cards) != len(ids) or any(not isinstance(c, dict) for c in cards)
            or {c.get('cardId') for c in cards} != set(ids)
            or any(c.get('note') != note_id for c in cards)):
        raise PublishError('Card identities do not match the note.')
    if not isinstance(reviews, dict) or set(reviews) != {str(i) for i in ids}:
        raise PublishError('Review-log coverage does not match the card IDs.')
    if any(not isinstance(log, list) or any(not isinstance(r, dict) for r in log) for log in reviews.values()):
        raise PublishError('Invalid review logs.')
    note['cards'] = sorted(ids)
    note['tags'] = sorted(note['tags'])
    if client.call('getActiveProfile') != profile:
        raise PublishError('Active profile changed during snapshot.')
    return {'format': 1, 'profile': profile, 'note': note,
            'model': {'fields': names, 'templates': templates, 'styling': styling},
            'cards': sorted(cards, key=lambda c: c['cardId']), 'reviews': reviews}


def meaningful(value):
    if not isinstance(value, str):
        return False
    # Preserve recognized media as content, but reject empty HTML and hidden script/style text.
    value = re.sub(r'<(script|style)\b[^>]*>.*?</\1\s*>', '', value, flags=re.I | re.S)
    value = re.sub(r'<!--.*?-->', '', value, flags=re.S)
    if re.search(r'<img\b[^>]*\bsrc\s*=\s*[\"\'][^\"\']+|\[sound:[^\]]+\]', value, re.I):
        return True
    value = html.unescape(re.sub(r'<[^>]*>', '', value))
    return bool(value.replace('\u200b', '').replace('\ufeff', '').strip())


def validate_update(before, fields):
    if before.get('format') != 1 or not isinstance(fields, dict) or not fields:
        raise PublishError('A format-1 snapshot and a nonempty fields object are required.')
    names = before['model']['fields']
    old = before['note']['fields']
    if not isinstance(names, list) or not names or set(old) != set(names):
        raise PublishError('The snapshot does not cover every model field.')
    if set(fields) - set(names):
        raise PublishError('Unknown fields: ' + ', '.join(sorted(set(fields) - set(names))))
    if 'SourceId' in fields and fields['SourceId'] != old['SourceId']['value']:
        raise PublishError('SourceId is immutable; update content fields only.')
    if any(not meaningful(v) for v in fields.values()):
        raise PublishError('Updated fields must be nonblank strings with content.')
    templates = before['model']['templates']
    if not isinstance(templates, dict) or not templates:
        raise PublishError('Missing templates.')
    referenced = set()
    for template in templates.values():
        for side in ('Front', 'Back'):
            value = template.get(side)
            if not isinstance(value, str) or not value.strip():
                raise PublishError('Both template sides must be nonempty strings.')
            if re.search(r'<\s*script\b', value, re.I):
                raise PublishError('Scripted templates are unsupported.')
            tokens = re.findall(r'{{(.*?)}}', value, re.S)
            referenced.update(t.strip() for t in tokens if t.strip() in names)
            if any(re.search(r'(^\s*[#^/])|\bcloze\s*:', t, re.I) for t in tokens):
                raise PublishError('Cloze and conditional templates require a separate migration workflow.')
            allowed = set(names) | {'FrontSide', 'Tags', 'Type', 'Deck', 'Subdeck', 'Card'}
            if any(t.strip() not in allowed for t in tokens):
                raise PublishError('Only direct field references and ordinary built-ins are supported.')
            if '{{' in re.sub(r'{{.*?}}', '', value, flags=re.S):
                raise PublishError('Malformed template expression.')
    if not before['cards']:
        raise PublishError('No existing cards to preserve.')
    for card in before['cards']:
        missing = CARD_REQUIRED - set(card)
        if missing:
            raise PublishError('AnkiConnect does not expose required card properties: ' + ', '.join(sorted(missing)))
    if sorted(c['ord'] for c in before['cards']) != list(range(len(templates))):
        raise PublishError('Existing cards must cover exactly every template ordinal; possible card generation change.')
    if any(not meaningful(old[name]['value']) for name in referenced & set(fields)):
        raise PublishError('Cannot update a previously blank template-referenced field; possible card generation change.')


def preserved(before, after, fields):
    expected = copy.deepcopy(before)
    for name, value in fields.items():
        expected['note']['fields'][name]['value'] = value
    actual = copy.deepcopy(after)
    for item in (expected, actual):
        item['note'].pop('mod', None)
        item['cards'] = [{k: v for k, v in card.items() if k not in CARD_CONTENT}
                         for card in item['cards']]
    return expected == actual


def checkpoint_prefix(base):
    token = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    base = Path(base)
    return str(base.with_name(base.stem + '.' + token))


def coverage(before):
    return {'verified': {'profile_model_templates_styling_note_identity_tags_other_fields': True,
                         'card_properties': sorted(set.intersection(*(set(c) for c in before['cards'])) - CARD_CONTENT),
                         'all_returned_card_properties_unchanged': True, 'returned_review_logs_unchanged': True},
            'limitations': 'Only properties exposed by AnkiConnect were checked. Unexposed FSRS state and '
                           'other database state were not checked. No atomic lock prevents concurrent edits or reviews.'}


def verify_note(client, note_id, fields, before, checkpoint_base):
    if not isinstance(before.get('note'), dict) or before['note'].get('noteId') != note_id:
        raise PublishError('Original checkpoint note ID differs from the requested note ID. No request made.')
    validate_update(before, fields)
    after_path = checkpoint_prefix(checkpoint_base) + '.verification.json'
    try:
        after = snapshot(client, note_id)
        save(after_path, after)
    except Exception as exc:
        save(after_path, {'snapshot_error': str(exc), 'noteId': note_id})
        raise PublishError(f'Verification could not complete. No Anki write made. Inspect {after_path}.') from exc
    if not preserved(before, after, fields):
        raise PublishError(f'Verification mismatch against original checkpoint. No Anki write made. Inspect {after_path}.')
    return {'status': 'verified', 'noteId': note_id, 'before': str(checkpoint_base),
            'after': after_path, **coverage(before)}


def update_note(client, note_id, fields, expected, checkpoint_base):
    before = snapshot(client, note_id)
    if before != expected:
        raise PublishError('Stale snapshot: profile, note, cards, model, or reviews changed. No write made.')
    validate_update(before, fields)
    if all(before['note']['fields'][k]['value'] == v for k, v in fields.items()):
        return {'status': 'no-op', 'noteId': note_id}
    prefix = checkpoint_prefix(checkpoint_base)
    before_path, after_path = prefix + '.prewrite.json', prefix + '.after.json'
    save(before_path, before)
    error = None
    try:
        client.call('updateNoteFields', note={'id': note_id, 'fields': fields})
    except Exception as exc:
        error = str(exc)
    try:
        after = snapshot(client, note_id)
        save(after_path, after)
    except Exception as exc:
        save(after_path, {'snapshot_error': str(exc), 'mutation_error': error, 'noteId': note_id})
        raise PublishError(f'Outcome uncertain; no retry or rollback. Check {before_path} and {after_path}.') from exc
    if error or not preserved(before, after, fields):
        raise PublishError(f'Update failed or preservation mismatch; no retry or rollback. '
                           f'Inspect {before_path} and {after_path}. Mutation error: {error}')
    return {'status': 'updated', 'noteId': note_id, 'before': before_path, 'after': after_path,
            **coverage(before)}


def generic_write(client, action, params):
    if action not in WRITE_ACTIONS:
        raise PublishError('Unsupported write action.')
    if action == 'addNote':
        note = params.get('note', {})
        if note.get('options', {}).get('allowDuplicate') is not False:
            raise PublishError('addNote requires options.allowDuplicate=false.')
        fields, tags = note.get('fields', {}), note.get('tags', [])
        field_identity = isinstance(fields, dict) and meaningful(fields.get('SourceId'))
        tag_identity = isinstance(tags, list) and any(isinstance(t, str) and re.fullmatch(r'anki-publish::source::[A-Za-z0-9_-]+', t) for t in tags)
        if not field_identity and not tag_identity:
            raise PublishError('addNote requires a nonblank SourceId field or anki-publish::source::<id> tag.')
    return client.call(action, **params)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=float, default=10)
    sub = parser.add_subparsers(dest='command', required=True)
    for command, actions in (('read', READ_ACTIONS), ('write', WRITE_ACTIONS)):
        p = sub.add_parser(command)
        p.add_argument('action', choices=sorted(actions))
        p.add_argument('--params', required=True, help='Path to a JSON object')
    p = sub.add_parser('snapshot')
    p.add_argument('note_id', type=int)
    p.add_argument('--out', required=True)
    for command in ('update', 'verify'):
        p = sub.add_parser(command)
        p.add_argument('note_id', type=int)
        p.add_argument('--fields', required=True)
        p.add_argument('--before', required=True)
    args = parser.parse_args(argv)
    try:
        client = Client(timeout=args.timeout)
        if args.command == 'read':
            result = client.call(args.action, **json_object(args.params))
        elif args.command == 'write':
            result = generic_write(client, args.action, json_object(args.params))
        elif args.command == 'snapshot':
            result = snapshot(client, args.note_id)
            save(args.out, result)
            result = {'status': 'snapshot', 'path': args.out, 'noteId': args.note_id}
        else:
            operation = update_note if args.command == 'update' else verify_note
            result = operation(client, args.note_id, json_object(args.fields), json_object(args.before), args.before)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (PublishError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
