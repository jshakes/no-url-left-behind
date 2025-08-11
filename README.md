# No URL Left Behind (nulb)

A tool for detecting 404 errors during website migrations by checking URLs from sitemap.xml files against a new domain.

## Installation

```bash
pip install nulb
```

## Usage

```bash
nulb <sitemap_url> <old_root> <new_domain>
```

### Examples

Basic check:
```bash
nulb https://oldsite.com/sitemap.xml https://oldsite.com https://newsite.com
```

With custom delay and output file:
```bash
nulb https://example.com/sitemap.xml https://example.com https://new-example.com --delay 0.5 --output report.txt
```

Check only for 404s (skip meta comparison):
```bash
nulb https://mysite.com/sitemap.xml https://mysite.com https://newsite.com --skip-meta
```

Fast check with output file:
```bash
nulb https://blog.com/sitemap.xml https://blog.com https://newblog.com --delay 0 --output migration-check.txt
```

### Options

- `--delay SECONDS` - Delay between requests (default: 0.1)
- `--output FILE` - Save report to file
- `--skip-meta` - Check 404s only, skip meta comparison

## Requirements

- Python 3.7+

## License

MIT

## Author

[James Shakespeare](https://jshakespeare.com) (j@jshakespeare.com)