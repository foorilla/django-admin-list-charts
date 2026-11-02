"""Publish browser captures into docs; approve baselines only after visual review."""
import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMES = [f'{example}-{theme}-{size}.png'
         for example in ('visits', 'commerce', 'memberships', 'publishing',
                         'visits-counts', 'commerce-counts', 'memberships-counts', 'publishing-counts')
         for theme in ('light', 'dark') for size in ('desktop', 'mobile')]
NAMES += [f'dense-history-{theme}-desktop.png' for theme in ('light', 'dark')]
NAMES += [f'dense-inspection-{theme}-desktop.png' for theme in ('light', 'dark')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'test-results/gallery')
    parser.add_argument('--approve-baselines', action='store_true')
    parser.add_argument('--check', action='store_true', help='Require all gallery images and approved baselines.')
    args = parser.parse_args()
    if args.check:
        required = [ROOT / 'docs/gallery' / name for name in NAMES]
        missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
        if missing:
            raise SystemExit('Visual release gate pending: capture and review all gallery scenarios.\n' + '\n'.join(missing))
        return
    missing = [name for name in NAMES if not (args.source / name).exists()]
    if missing:
        raise SystemExit('Run the complete Playwright gallery first; missing: ' + ', '.join(missing))
    if not args.approve_baselines:
        parser.error('Review captures, then pass --approve-baselines to update the gallery and visual baselines.')
    gallery = ROOT / 'docs/gallery'
    gallery.mkdir(exist_ok=True)
    for name in NAMES:
        shutil.copyfile(args.source / name, gallery / name)
    lines = ['# Gallery', '', 'Timeline-only and counts-enabled charts adapt to desktop and mobile containers in Django’s light and dark themes.', '']
    for example in ('visits', 'commerce', 'memberships', 'publishing'):
        captions = {
            'visits': 'Traffic over time with channel, device and conversion distributions.',
            'commerce': 'Order volume, payment rates and distributions by status and channel.',
            'memberships': 'Account growth, activity rates and membership tiers.',
            'publishing': 'Publishing history, remote-work rates and job status.',
        }
        lines.extend([f'## {example.title()}', '', captions[example], ''])
        for theme in ('light', 'dark'):
            for size in ('desktop', 'mobile'):
                for mode in ('', '-counts'):
                    name = f'{example}{mode}-{theme}-{size}.png'
                    caption = 'counts enabled' if mode else 'timeline only'
                    lines.extend([f'![{example.title()}, {caption}, {theme}, {size}](gallery/{name})', ''])
    lines.extend(['## Long histories', '', 'Thin lines retain detail across dense timelines.', ''])
    for theme in ('light', 'dark'):
        lines.extend([f'![Long history, {theme}](gallery/dense-history-{theme}-desktop.png)', ''])
    lines.extend(['Hover or focus a point for exact values and a position guide.', ''])
    for theme in ('light', 'dark'):
        lines.extend([f'![Inspecting a point, {theme}](gallery/dense-inspection-{theme}-desktop.png)', ''])
    (ROOT / 'docs/gallery.md').write_text('\n'.join(lines))
    for path, prefix in ((ROOT / 'README.md', 'docs/gallery/'),
                         (ROOT / 'docs/index.md', 'gallery/')):
        document = path.read_text()
        start, end = '<!-- gallery:start -->', '<!-- gallery:end -->'
        images = '\n\n'.join(
            f'![Visits, {caption}]({prefix}visits{mode}-light-desktop.png)'
            for mode, caption in (('', 'timeline only'), ('-counts', 'counts enabled')))
        before, tail = document.split(start, 1)
        _, after = tail.split(end, 1)
        path.write_text(before + start + '\n' + images + '\n' + end + after)


if __name__ == '__main__':
    main()
