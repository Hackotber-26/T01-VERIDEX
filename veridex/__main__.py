import argparse
import json
from pathlib import Path
from .review import review

def main():
    parser = argparse.ArgumentParser(description='VERIDEX pothole repair evidence review')
    parser.add_argument('--before', required=True)
    parser.add_argument('--after', required=True)
    parser.add_argument('--roi', nargs=4, type=float, required=True, metavar=('X1','Y1','X2','Y2'),
                        help='Normalized target box on the EXIF-oriented original image')
    parser.add_argument('--output', help='Optional result JSON path')
    args = parser.parse_args()
    try:
        result = review(args.before, args.after, args.roi)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    text = json.dumps(result, indent=2)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text+'\n')
    print(text)

if __name__ == '__main__':
    main()
