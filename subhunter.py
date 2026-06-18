#!/usr/bin/env python3
"""
SubHunter - A Python-based subdomain finder tool
Usage: python subhunter.py -d example.com -w wordlist.txt [options]
"""

import argparse
import asyncio
import aiohttp
import sys
import os
import json
import time
import signal
from datetime import datetime
from urllib.parse import urlparse
from colorama import Fore, Style, init

# Initialize colorama for cross-platform colored output
init(autoreset=True)

# ─────────────────────────────────────────────
#  Banner
# ─────────────────────────────────────────────
BANNER = f"""
{Fore.CYAN}
  ██████  ██    ██ ██████  ██   ██ ██    ██ ███    ██ ████████ ███████ ██████  
  ██      ██    ██ ██   ██ ██   ██ ██    ██ ████   ██    ██    ██      ██   ██ 
  ███████ ██    ██ ██████  ███████ ██    ██ ██ ██  ██    ██    █████   ██████  
       ██ ██    ██ ██   ██ ██   ██ ██    ██ ██  ██ ██    ██    ██      ██   ██ 
  ██████   ██████  ██████  ██   ██  ██████  ██   ████    ██    ███████ ██   ██ 
{Style.RESET_ALL}
  {Fore.YELLOW}SubHunter v1.0{Style.RESET_ALL} — Fast Async Subdomain Discovery Tool
  {Fore.WHITE}Author: Mannat Khandelwal{Style.RESET_ALL}
  {'─'*70}
"""

# ─────────────────────────────────────────────
#  Color Helpers
# ─────────────────────────────────────────────
def info(msg):    print(f"  {Fore.CYAN}[*]{Style.RESET_ALL} {msg}")
def success(msg): print(f"  {Fore.GREEN}[+]{Style.RESET_ALL} {msg}")
def warn(msg):    print(f"  {Fore.YELLOW}[!]{Style.RESET_ALL} {msg}")
def error(msg):   print(f"  {Fore.RED}[-]{Style.RESET_ALL} {msg}")
def live(msg):    print(f"  {Fore.GREEN}[✓]{Style.RESET_ALL} {msg}")

STATUS_COLORS = {
    1: Fore.WHITE,    # 1xx Informational
    2: Fore.GREEN,    # 2xx Success
    3: Fore.CYAN,     # 3xx Redirect
    4: Fore.YELLOW,   # 4xx Client Error
    5: Fore.RED,      # 5xx Server Error
}

def colorize_status(code):
    color = STATUS_COLORS.get(code // 100, Fore.WHITE)
    return f"{color}[{code}]{Style.RESET_ALL}"

# ─────────────────────────────────────────────
#  Argument Parser
# ─────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(
        prog="subhunter",
        description="SubHunter - Fast Async Subdomain Discovery Tool",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples:
  python subhunter.py -d example.com -w wordlist.txt
  python subhunter.py -d example.com -w wordlist.txt --https-only
  python subhunter.py -d example.com -w wordlist.txt --sc 200,301,403
  python subhunter.py -d example.com -w wordlist.txt --exclude-sc 404,500
  python subhunter.py -d example.com -w wordlist.txt --ext php,html
  python subhunter.py -d example.com -w wordlist.txt -o results.txt --json
        """
    )

    # Target
    target = parser.add_argument_group("Target")
    target.add_argument("-d", "--domain", required=True, help="Target domain (e.g. example.com)")
    target.add_argument("-u", "--url", help="Full URL (overrides -d, supports http/https)")

    # Wordlist
    wl = parser.add_argument_group("Wordlist")
    wl.add_argument("-w", "--wordlist", required=True, help="Path to wordlist file")

    # Protocol
    proto = parser.add_argument_group("Protocol")
    proto.add_argument("--http-only",  action="store_true", help="Only probe over HTTP")
    proto.add_argument("--https-only", action="store_true", help="Only probe over HTTPS")
    proto.add_argument("--both",       action="store_true", default=True,
                       help="Probe both HTTP and HTTPS (default)")

    # Status Code Filters
    sc = parser.add_argument_group("Status Code Filters")
    sc.add_argument("--sc",         metavar="CODES",
                    help="Only show responses with these status codes (comma-separated, e.g. 200,301)")
    sc.add_argument("--exclude-sc", metavar="CODES",
                    help="Exclude responses with these status codes (comma-separated, e.g. 404,500)")

    # Extensions
    ext = parser.add_argument_group("Extensions")
    ext.add_argument("--ext",         metavar="EXTS",
                     help="Include only these extensions (comma-separated, e.g. php,html,js)")
    ext.add_argument("--exclude-ext", metavar="EXTS",
                     help="Exclude these extensions (comma-separated, e.g. png,jpg,css)")

    # Performance
    perf = parser.add_argument_group("Performance")
    perf.add_argument("-t", "--threads",  type=int, default=50,
                      help="Number of concurrent requests (default: 50)")
    perf.add_argument("--timeout",        type=int, default=5,
                      help="Request timeout in seconds (default: 5)")
    perf.add_argument("--delay",          type=float, default=0,
                      help="Delay between requests in seconds (default: 0)")
    perf.add_argument("--retries",        type=int, default=1,
                      help="Number of retries for failed requests (default: 1)")

    # HTTP Settings
    http = parser.add_argument_group("HTTP Settings")
    http.add_argument("-H", "--header",   action="append", dest="headers", metavar="HEADER",
                      help="Custom header (e.g. 'X-Custom: value'). Repeatable.")
    http.add_argument("--user-agent",     default="SubHunter/1.0",
                      help="Custom User-Agent string")
    http.add_argument("--follow-redirects", action="store_true", default=True,
                      help="Follow HTTP redirects (default: True)")
    http.add_argument("--no-redirects",   action="store_true",
                      help="Do not follow HTTP redirects")

    # Output
    out = parser.add_argument_group("Output")
    out.add_argument("-o", "--output",    help="Save results to file")
    out.add_argument("--json",            action="store_true",
                     help="Output in JSON format (use with -o)")
    out.add_argument("--csv",             action="store_true",
                     help="Output in CSV format (use with -o)")
    out.add_argument("-v", "--verbose",   action="store_true",
                     help="Verbose output (show filtered results too)")
    out.add_argument("-q", "--quiet",     action="store_true",
                     help="Quiet mode (only show results, no banner/stats)")
    out.add_argument("--no-color",        action="store_true",
                     help="Disable colored output")

    return parser.parse_args()

# ─────────────────────────────────────────────
#  Wordlist Loader
# ─────────────────────────────────────────────
def load_wordlist(path):
    if not os.path.isfile(path):
        error(f"Wordlist not found: {path}")
        sys.exit(1)
    with open(path, "r", errors="ignore") as f:
        words = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return words

# ─────────────────────────────────────────────
#  URL Builder
# ─────────────────────────────────────────────
def build_urls(domain, word, schemes, extensions):
    """Build list of URLs to probe for a given word."""
    urls = []
    domain = domain.lstrip(".")

    if extensions:
        for ext in extensions:
            ext = ext.lstrip(".")
            path = f"{word}.{ext}"
            for scheme in schemes:
                urls.append(f"{scheme}://{path}.{domain}")
                urls.append(f"{scheme}://{domain}/{path}")
        for scheme in schemes:
            urls.append(f"{scheme}://{word}.{domain}")
    else:
        for scheme in schemes:
            urls.append(f"{scheme}://{word}.{domain}")

    return urls

# ─────────────────────────────────────────────
#  Core Prober
# ─────────────────────────────────────────────
class SubHunter:
    def __init__(self, args):
        self.args = args
        self.results = []
        self.probed = 0
        self.found = 0
        self.skipped = 0
        self.start_time = time.time()
        self.semaphore = None

        # Determine schemes
        if args.http_only:
            self.schemes = ["http"]
        elif args.https_only:
            self.schemes = ["https"]
        else:
            self.schemes = ["https", "http"]

        # Status code filters
        self.include_sc = set()
        self.exclude_sc = set()
        if args.sc:
            self.include_sc = {int(c.strip()) for c in args.sc.split(",") if c.strip()}
        if args.exclude_sc:
            self.exclude_sc = {int(c.strip()) for c in args.exclude_sc.split(",") if c.strip()}

        # Extension filters
        self.include_ext = []
        self.exclude_ext = []
        if args.ext:
            self.include_ext = [e.strip().lstrip(".") for e in args.ext.split(",")]
        if args.exclude_ext:
            self.exclude_ext = [e.strip().lstrip(".") for e in args.exclude_ext.split(",")]

        # Custom headers
        self.custom_headers = {"User-Agent": args.user_agent}
        if args.headers:
            for h in args.headers:
                if ":" in h:
                    k, v = h.split(":", 1)
                    self.custom_headers[k.strip()] = v.strip()

    def should_include(self, url, status_code):
        """Decide whether a result passes all filters."""
        parsed = urlparse(url)
        path = parsed.path
        if "." in path.split("/")[-1]:
            ext = path.rsplit(".", 1)[-1].lower()
        else:
            ext = ""

        if self.include_ext and ext not in self.include_ext:
            return False
        if self.exclude_ext and ext in self.exclude_ext:
            return False
        if self.include_sc and status_code not in self.include_sc:
            return False
        if self.exclude_sc and status_code in self.exclude_sc:
            return False

        return True

    async def probe_url(self, session, url, retries_left):
        """Probe a single URL and return result dict."""
        follow = self.args.follow_redirects and not self.args.no_redirects
        try:
            async with session.get(
                url,
                headers=self.custom_headers,
                allow_redirects=follow,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=self.args.timeout),
            ) as resp:
                status  = resp.status
                length  = resp.headers.get("Content-Length", "-")
                server  = resp.headers.get("Server", "-")
                ctype   = resp.headers.get("Content-Type", "-").split(";")[0].strip()
                final   = str(resp.url)
                return {
                    "url":          url,
                    "final_url":    final,
                    "status":       status,
                    "length":       length,
                    "server":       server,
                    "content_type": ctype,
                    "live":         True,
                    "redirected":   (final != url),
                }
        except asyncio.TimeoutError:
            if retries_left > 0:
                return await self.probe_url(session, url, retries_left - 1)
            return {"url": url, "live": False, "error": "Timeout"}
        except aiohttp.ClientConnectorError:
            if retries_left > 0:
                return await self.probe_url(session, url, retries_left - 1)
            return {"url": url, "live": False, "error": "Connection refused"}
        except Exception as e:
            return {"url": url, "live": False, "error": str(e)[:80]}

    async def worker(self, session, url):
        """Worker: probe URL, show only live results that pass filters."""
        async with self.semaphore:
            if self.args.delay:
                await asyncio.sleep(self.args.delay)

            result = await self.probe_url(session, url, self.args.retries)
            self.probed += 1

            if result["live"]:
                status = result["status"]
                passed = self.should_include(url, status)

                if passed:
                    self.found += 1
                    self.results.append(result)

                    arrow = f"  → {result['final_url']}" if result["redirected"] else ""
                    line  = (
                        f"  {colorize_status(status)} "
                        f"{Fore.GREEN}{url}{Style.RESET_ALL}"
                        f"  [{result['length']}B]"
                        f"  [{result['server']}]"
                        f"{Fore.CYAN}{arrow}{Style.RESET_ALL}"
                    )
                    # Clear progress line before printing a result
                    sys.stdout.write("\r" + " " * 80 + "\r")
                    sys.stdout.flush()
                    live(line) if not self.args.quiet else print(url)

                else:
                    self.skipped += 1
                    if self.args.verbose:
                        sys.stdout.write("\r" + " " * 80 + "\r")
                        warn(f"{colorize_status(status)} {url}  (filtered by SC/ext rules)")

            else:
                # Dead URL — silently drop, only show in verbose mode
                self.skipped += 1
                if self.args.verbose:
                    sys.stdout.write("\r" + " " * 80 + "\r")
                    warn(f"{url}  — {result.get('error', 'No response')}")

            # Live progress bar
            elapsed = time.time() - self.start_time
            rps = self.probed / elapsed if elapsed > 0 else 0
            sys.stdout.write(
                f"\r  {Fore.WHITE}Progress:{Style.RESET_ALL} "
                f"{self.probed} probed | "
                f"{Fore.GREEN}{self.found} live found{Style.RESET_ALL} | "
                f"{rps:.1f} req/s    "
            )
            sys.stdout.flush()

    async def run(self, words):
        self.semaphore = asyncio.Semaphore(self.args.threads)

        domain = self.args.domain
        if self.args.url:
            parsed = urlparse(self.args.url if "://" in self.args.url else "http://" + self.args.url)
            domain = parsed.netloc or parsed.path

        all_urls = []
        for word in words:
            urls = build_urls(domain, word, self.schemes, self.include_ext)
            all_urls.extend(urls)

        total = len(all_urls)
        if not self.args.quiet:
            info(f"Target domain   : {Fore.YELLOW}{domain}{Style.RESET_ALL}")
            info(f"Wordlist words  : {Fore.YELLOW}{len(words):,}{Style.RESET_ALL}")
            info(f"Total URLs      : {Fore.YELLOW}{total:,}{Style.RESET_ALL}")
            info(f"Schemes         : {Fore.YELLOW}{', '.join(self.schemes)}{Style.RESET_ALL}")
            info(f"Concurrency     : {Fore.YELLOW}{self.args.threads}{Style.RESET_ALL}")
            info(f"Timeout         : {Fore.YELLOW}{self.args.timeout}s{Style.RESET_ALL}")
            if self.include_sc:
                info(f"Include SC      : {Fore.YELLOW}{', '.join(map(str, self.include_sc))}{Style.RESET_ALL}")
            if self.exclude_sc:
                info(f"Exclude SC      : {Fore.YELLOW}{', '.join(map(str, self.exclude_sc))}{Style.RESET_ALL}")
            if self.include_ext:
                info(f"Include Ext     : {Fore.YELLOW}{', '.join(self.include_ext)}{Style.RESET_ALL}")
            if self.exclude_ext:
                info(f"Exclude Ext     : {Fore.YELLOW}{', '.join(self.exclude_ext)}{Style.RESET_ALL}")
            print(f"\n  {'─'*70}")
            print(f"  {Fore.WHITE}{'STATUS':<10}{'URL':<55}{'SIZE':<12}{'SERVER'}{Style.RESET_ALL}")
            print(f"  {'─'*70}")

        connector = aiohttp.TCPConnector(
            limit=self.args.threads,
            limit_per_host=10,
            ssl=False,
            ttl_dns_cache=300,
        )

        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [self.worker(session, url) for url in all_urls]
            await asyncio.gather(*tasks)

        print()  # newline after progress bar

# ─────────────────────────────────────────────
#  Output Formatters
# ─────────────────────────────────────────────
def save_results(results, path, fmt_json=False, fmt_csv=False):
    if fmt_json:
        with open(path, "w") as f:
            json.dump(results, f, indent=2)
    elif fmt_csv:
        import csv
        with open(path, "w", newline="") as f:
            if not results:
                return
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
    else:
        with open(path, "w") as f:
            for r in results:
                f.write(f"{r['status']}\t{r['url']}\t{r.get('length','-')}\t{r.get('server','-')}\n")

# ─────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────
def main():
    args = parse_args()

    if args.no_color:
        import colorama
        colorama.deinit()

    if not args.quiet:
        print(BANNER)

    def handle_sigint(sig, frame):
        print(f"\n\n  {Fore.YELLOW}[!]{Style.RESET_ALL} Interrupted by user. Saving partial results...")
        sys.exit(0)
    signal.signal(signal.SIGINT, handle_sigint)

    words = load_wordlist(args.wordlist)
    if not args.quiet:
        info(f"Loaded {len(words):,} words from {args.wordlist}")

    hunter = SubHunter(args)

    start = datetime.now()
    try:
        asyncio.run(hunter.run(words))
    except KeyboardInterrupt:
        pass

    elapsed = (datetime.now() - start).total_seconds()

    if not args.quiet:
        print(f"\n  {'─'*70}")
        print(f"  {Fore.CYAN}SCAN COMPLETE{Style.RESET_ALL}")
        print(f"  {'─'*70}")
        success(f"Probed   : {hunter.probed:,} URLs")
        success(f"Found    : {Fore.GREEN}{hunter.found:,}{Style.RESET_ALL} live subdomains")
        info(   f"Duration : {elapsed:.2f}s  ({hunter.probed/elapsed:.1f} req/s avg)" if elapsed > 0 else "")

    if args.output and hunter.results:
        save_results(hunter.results, args.output, args.json, args.csv)
        success(f"Results saved to: {Fore.YELLOW}{args.output}{Style.RESET_ALL}")
    elif args.output:
        warn("No live subdomains found to save.")

if __name__ == "__main__":
    main()
