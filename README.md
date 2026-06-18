# Subhunter

**Fast Async Subdomain Discovery Tool**

**Author: Mannat Khandelwal**

---

## Installation

```bash
pip install aiohttp colorama
```

---

## Usage

```
python subhunter.py -d <domain> -w <wordlist> [OPTIONS]
```

SubHunter only shows **live subdomains** by default — dead/unreachable hosts are silently dropped. Use `-v` to also see filtered/dead URLs.

---

## All Flags

### Target
| Flag | Description |
|------|-------------|
| `-d`, `--domain` | Target domain (e.g. `example.com`) |
| `-u`, `--url`    | Full URL override (e.g. `https://example.com`) |

### Wordlist
| Flag | Description |
|------|-------------|
| `-w`, `--wordlist` | Path to wordlist file |

### Protocol
| Flag | Description |
|------|-------------|
| `--http-only`  | Only probe over HTTP |
| `--https-only` | Only probe over HTTPS |
| `--both`       | Probe both HTTP & HTTPS (default) |

### Status Code Filters
| Flag | Description |
|------|-------------|
| `--sc 200,301`         | Only show these status codes |
| `--exclude-sc 404,500` | Hide these status codes |

### Extension Filters
| Flag | Description |
|------|-------------|
| `--ext php,html,js`         | Only include URLs ending in these extensions |
| `--exclude-ext png,jpg,css` | Exclude URLs with these extensions |

### Performance
| Flag | Default | Description |
|------|---------|-------------|
| `-t`, `--threads` | 50  | Concurrent requests |
| `--timeout`       | 5s  | Request timeout |
| `--delay`         | 0   | Delay between requests (seconds) |
| `--retries`       | 1   | Retry failed requests N times |

### HTTP Settings
| Flag | Description |
|------|-------------|
| `-H "Header: Value"` | Add custom HTTP header (repeatable) |
| `--user-agent`       | Custom User-Agent string |
| `--no-redirects`     | Don't follow HTTP redirects |

### Output
| Flag | Description |
|------|-------------|
| `-o results.txt` | Save results to file |
| `--json`         | Save as JSON (use with `-o`) |
| `--csv`          | Save as CSV (use with `-o`) |
| `-v`, `--verbose`| Also show filtered and dead URLs |
| `-q`, `--quiet`  | Quiet mode — only print found URLs |
| `--no-color`     | Disable colored output |

---

## Examples

```bash
# Basic scan (shows only live subdomains)
python subhunter.py -d example.com -w subdomains.txt

# HTTPS only, save to JSON
python subhunter.py -d example.com -w subdomains.txt --https-only -o out.json --json

# Only show 200 and 301 responses
python subhunter.py -d example.com -w subdomains.txt --sc 200,301

# Exclude 404 and 500
python subhunter.py -d example.com -w subdomains.txt --exclude-sc 404,500

# High concurrency with custom header
python subhunter.py -d example.com -w subdomains.txt -t 100 -H "X-Bug-Bounty: hunter"

# Quiet mode — pipe live subdomains to another tool
python subhunter.py -d example.com -w subdomains.txt -q | tee live.txt

# Verbose — see everything including dead hosts
python subhunter.py -d example.com -w subdomains.txt -v
```

---

## Recommended Wordlists

Use **subdomain wordlists** (not directory wordlists) for best results:

| File | Source |
|------|--------|
| `subdomains.txt` | Included with SubHunter (514 curated entries) |
| `subdomains-top1million-5000.txt` | SecLists/Discovery/DNS/ |
| `namelist.txt` | SecLists/Discovery/DNS/ |
| `bitquark-subdomains-top100000.txt` | SecLists/Discovery/DNS/ |

> **Avoid** `raft-small-directories.txt` and other web-path wordlists — they are for directory brute-forcing, not subdomain discovery.

---

## How It Works

1. Reads the wordlist and builds subdomain URLs (`word.domain.com`)
2. If `--ext` is provided, also builds path-based URLs (`domain.com/word.php`)
3. Fires async HTTP requests (both HTTP + HTTPS by default)
4. Only live (responding) hosts are shown — dead hosts are silently dropped
5. Applies status code and extension filters to the live results
6. Prints color-coded output: status, URL, content size, server header, redirect info
7. Optionally saves to `.txt`, `.json`, or `.csv`

---

## Architecture

```
subhunter.py
├── parse_args()        ← all CLI flags
├── load_wordlist()     ← read & clean wordlist
├── build_urls()        ← generate URL permutations per word
└── SubHunter class
    ├── __init__()      ← initialize filters, schemes, headers
    ├── should_include()← apply status code + extension filters
    ├── probe_url()     ← async HTTP request with retry logic
    ├── worker()        ← per-URL coroutine — prints live results only
    └── run()           ← build task pool, run asyncio.gather()
```

---

## Ethical Use

> This tool is for **educational and authorized testing purposes only.**  
> Only scan domains you own or have **explicit written permission** to test.  
> Unauthorized scanning may violate computer crime laws (IT Act 2000 in India).
