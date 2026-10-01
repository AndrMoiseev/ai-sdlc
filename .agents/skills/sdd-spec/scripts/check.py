"""Read-only structural check; approvals are reported independently of exit status."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', required=True, type=Path)
    parser.add_argument('--change', required=True)
    parser.add_argument('--stage', required=True, choices=('documents', 'plan'))
    args = parser.parse_args(argv)
    result = {'schema_version': 1, 'stage': args.stage, 'errors': [], 'warnings': [],
              'review_status': {'status': 'not_checked'},
              'approval_status': {'status': 'not_checked'}}
    try:
        from lib.documents import InputError, ValidationError
        from lib.paths import change_root
        from lib.validation import validate_documents
        from lib.reviews import review_status
    except ImportError as exc:
        result['errors'].append({'code': 'environment', 'path': '', 'element_id': None,
                                 'message': f'{exc}; run through uv with the locked skill project'})
        print(json.dumps(result, ensure_ascii=False))
        return 2
    try:
        project = args.project_root.resolve(strict=True)
        root = change_root(project, args.change)
        structure = validate_documents(project, root, args.stage)
        for key in ('errors', 'warnings'):
            result[key].extend(structure.get(key, []))
        for key in ('tasks', 'progress'):
            if key in structure:
                result[key] = structure[key]
        review = review_status(project, root, args.stage)
        for key in ('errors', 'warnings'):
            result[key].extend(review.get(key, []))
        for key in ('review_status', 'approval_status'):
            result[key] = review[key]
        if result['errors']:
            result['approval_status']['ready'] = False
        exit_code = 1 if result['errors'] else 0
    except (InputError, ValidationError, OSError, UnicodeError) as exc:
        result['errors'].append({'code': getattr(exc, 'code', 'input_unreadable'),
                                 'path': str(getattr(exc, 'path', args.project_root)),
                                 'element_id': getattr(exc, 'element_id', None),
                                 'message': getattr(exc, 'message', str(exc))})
        exit_code = 2 if isinstance(exc, (InputError, OSError, UnicodeError)) else 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
