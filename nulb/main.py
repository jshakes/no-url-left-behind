#!/usr/bin/env python3
"""
No URL Left Behind (nulb)

A tool for detecting 404 errors during website migrations by checking URLs from 
sitemap.xml files against a new domain.

Usage:
    nulb <sitemap_url> <old_root> <new_domain>

Example:
    nulb https://oldsite.com/sitemap.xml https://oldsite.com https://newsite.com
"""

import sys
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
import argparse
from datetime import datetime
import time
from bs4 import BeautifulSoup
import re
import threading
import signal


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[32m'
    RED = '\033[31m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'  # End color


class Spinner:
    """Animated spinner for showing progress."""
    def __init__(self, message="Loading..."):
        self.spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.message = message
        self.spinning = False
        self.thread = None
    
    def _spin(self):
        i = 0
        while self.spinning:
            sys.stdout.write(f"\r{self.spinner_chars[i % len(self.spinner_chars)]} {self.message}")
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1
    
    def start(self):
        self.spinning = True
        self.thread = threading.Thread(target=self._spin)
        self.thread.start()
    
    def stop(self):
        self.spinning = False
        if self.thread:
            self.thread.join()
        sys.stdout.write('\r' + ' ' * (len(self.message) + 5) + '\r')
        sys.stdout.flush()


def parse_sitemap(sitemap_url, show_spinner=True):
    """Parse sitemap.xml and extract all URLs."""
    if show_spinner:
        spinner = Spinner(f"Fetching sitemap from: {sitemap_url}")
        spinner.start()
    
    try:
        response = requests.get(sitemap_url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        if show_spinner:
            spinner.stop()
        print(f"Error fetching sitemap: {e}")
        sys.exit(1)

    if show_spinner:
        spinner.stop()
        print(f"Fetching sitemap from: {sitemap_url}")

    try:
        if show_spinner:
            spinner = Spinner("Processing sitemap XML...")
            spinner.start()
        
        root = ET.fromstring(response.content)

        # Handle namespace - sitemaps typically use this namespace
        namespace = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        urls = []

        # Check if this is a sitemap index or a regular sitemap
        sitemap_elements = root.findall(".//ns:sitemap", namespace)
        if sitemap_elements:
            if show_spinner:
                spinner.stop()
            print(
                f"Found sitemap index with {len(sitemap_elements)} sitemaps, processing each..."
            )
            for i, sitemap_elem in enumerate(sitemap_elements, 1):
                loc_elem = sitemap_elem.find("ns:loc", namespace)
                if loc_elem is not None:
                    print(
                        f"  Processing sitemap {i}/{len(sitemap_elements)}: {loc_elem.text}"
                    )
                    sub_urls = parse_sitemap(loc_elem.text, show_spinner=False)
                    urls.extend(sub_urls)
                    print(f"  Added {len(sub_urls)} URLs from this sitemap")
        else:
            # Regular sitemap with URL entries
            url_elements = root.findall(".//ns:url", namespace)
            for url_elem in url_elements:
                loc_elem = url_elem.find("ns:loc", namespace)
                if loc_elem is not None:
                    urls.append(loc_elem.text)

        if show_spinner:
            spinner.stop()
        print(f"Found {len(urls)} URLs in sitemap")
        return urls

    except ET.ParseError as e:
        if show_spinner:
            spinner.stop()
        print(f"Error parsing XML: {e}")
        sys.exit(1)


def extract_meta_info(html_content):
    """Extract meta title and description from HTML content."""
    if not html_content:
        return {"title": None, "description": None}
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract title
        title_tag = soup.find('title')
        title = title_tag.get_text().strip() if title_tag else None
        
        # Extract meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        description = None
        if meta_desc and meta_desc.get('content'):
            description = meta_desc.get('content').strip()
        
        return {"title": title, "description": description}
    except Exception as e:
        return {"title": None, "description": None, "error": str(e)}


def check_url(original_url, old_root, new_domain, skip_meta=False):
    """Check if a URL exists on the new domain and compare meta information."""
    # Remove the old root from the original URL to get the path
    if original_url.startswith(old_root):
        path = original_url[len(old_root) :]
    else:
        # If the URL doesn't start with old_root, extract path normally
        parsed_original = urlparse(original_url)
        path = parsed_original.path
        if parsed_original.query:
            path += f"?{parsed_original.query}"

    # Construct new URL
    new_url = urljoin(new_domain.rstrip("/") + "/", path.lstrip("/"))

    result = {
        "original_url": original_url,
        "new_url": new_url,
        "final_url": None,
        "status_code": None,
        "is_404": False,
        "is_redirect": False,
        "original_meta": {"title": None, "description": None},
        "new_meta": {"title": None, "description": None},
        "meta_matches": {"title": True, "description": True}
    }

    try:
        # Make request to new URL with a reasonable timeout and allow redirects
        new_response = requests.get(new_url, timeout=10, allow_redirects=True)
        result["status_code"] = new_response.status_code
        result["is_404"] = new_response.status_code == 404
        result["final_url"] = new_response.url
        
        # Check if we were redirected
        result["is_redirect"] = new_response.url != new_url
        
        # If new URL is not 404 and we're not skipping meta checks, get meta info and compare
        if not result["is_404"] and not skip_meta:
            # Get meta info from final URL (after any redirects)
            result["new_meta"] = extract_meta_info(new_response.text)
            
            # For redirects, we don't compare meta as they're expected to be different
            if result["is_redirect"]:
                # Mark meta as matching for redirects since they're considered successful
                result["meta_matches"]["title"] = True
                result["meta_matches"]["description"] = True
            else:
                # Get meta info from original URL for comparison
                try:
                    original_response = requests.get(original_url, timeout=10, allow_redirects=True)
                    if original_response.status_code == 200:
                        result["original_meta"] = extract_meta_info(original_response.text)
                except requests.RequestException:
                    # If we can't fetch original, leave meta as None
                    pass
                
                # Compare meta information only for non-redirects
                result["meta_matches"]["title"] = (
                    result["original_meta"]["title"] == result["new_meta"]["title"]
                    or result["original_meta"]["title"] is None
                    or result["new_meta"]["title"] is None
                )
                result["meta_matches"]["description"] = (
                    result["original_meta"]["description"] == result["new_meta"]["description"]
                    or result["original_meta"]["description"] is None
                    or result["new_meta"]["description"] is None
                )
            
        return result
        
    except requests.RequestException as e:
        result.update({
            "status_code": "ERROR",
            "error": str(e),
            "is_404": False,
        })
        return result


def check_url_with_spinner(original_url, old_root, new_domain, url_index, total_urls, skip_meta=False):
    """Check URL with animated spinner."""
    spinner_msg = f"Checking {url_index}/{total_urls}: {original_url[:50]}{'...' if len(original_url) > 50 else ''}"
    spinner = Spinner(spinner_msg)
    
    spinner.start()
    try:
        result = check_url(original_url, old_root, new_domain, skip_meta)
    finally:
        spinner.stop()
    
    return result


def print_result_list(result, url_index, total_urls, skip_meta=False):
    """Print results in a clean list format."""
    print(f"\n{Colors.CYAN}{'-' * 80}{Colors.END}")
    print(f"{Colors.BOLD}[{url_index:03d}/{total_urls:03d}]{Colors.END}")
    print(f"{Colors.BOLD}Original:{Colors.END} {result['original_url']}")
    print(f"{Colors.BOLD}New:{Colors.END}      {result['new_url']}")
    
    # Show final URL if redirected
    if result.get("is_redirect", False) and result.get("final_url"):
        print(f"{Colors.BOLD}Final:{Colors.END}    {result['final_url']}")
    
    # Status
    status_display = result.get("error", result["status_code"])
    if result["is_404"]:
        status_color = Colors.RED
        status_text = "404 NOT FOUND"
    elif result.get("is_redirect", False):
        status_color = Colors.GREEN
        status_text = f"REDIRECT ({status_display})"
    elif result["status_code"] == 200:
        status_color = Colors.GREEN
        status_text = f"OK ({status_display})"
    else:
        status_color = Colors.YELLOW
        status_text = f"WARN ({status_display})"
    
    print(f"{Colors.BOLD}Status:{Colors.END}   {status_color}{status_text}{Colors.END}")
    
    # Only show meta info for non-404 responses and if meta checking is enabled
    if not result["is_404"] and not skip_meta:
        # For redirects, show the final page meta but don't compare
        if result.get("is_redirect", False):
            title_value = result["new_meta"]["title"] or "(none)"
            desc_value = result["new_meta"]["description"] or "(none)"
            print(f"{Colors.BOLD}Title:{Colors.END}    {Colors.BLUE}REDIRECT{Colors.END} - {title_value}")
            print(f"{Colors.BOLD}Desc:{Colors.END}     {Colors.BLUE}REDIRECT{Colors.END} - {desc_value}")
        else:
            # Title comparison for non-redirects
            if result["meta_matches"]["title"]:
                title_value = result["new_meta"]["title"] or "(none)"
                print(f"{Colors.BOLD}Title:{Colors.END}    {Colors.GREEN}MATCH{Colors.END} - {title_value}")
            else:
                print(f"{Colors.BOLD}Title:{Colors.END}    {Colors.RED}DIFFERENT{Colors.END}")
                orig_title = result["original_meta"]["title"] or "(none)"
                new_title = result["new_meta"]["title"] or "(none)"
                print(f"         Original: {Colors.MAGENTA}{orig_title}{Colors.END}")
                print(f"         New:      {Colors.CYAN}{new_title}{Colors.END}")
            
            # Description comparison for non-redirects
            if result["meta_matches"]["description"]:
                desc_value = result["new_meta"]["description"] or "(none)"
                print(f"{Colors.BOLD}Desc:{Colors.END}     {Colors.GREEN}MATCH{Colors.END} - {desc_value}")
            else:
                print(f"{Colors.BOLD}Desc:{Colors.END}     {Colors.RED}DIFFERENT{Colors.END}")
                orig_desc = result["original_meta"]["description"] or "(none)"
                new_desc = result["new_meta"]["description"] or "(none)"
                print(f"         Original: {Colors.MAGENTA}{orig_desc}{Colors.END}")
                print(f"         New:      {Colors.CYAN}{new_desc}{Colors.END}")


# Global flag for graceful shutdown
interrupted = False

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    global interrupted
    interrupted = True
    print(f"\n\n{Colors.YELLOW}[!] Interrupt received. Finishing current check and generating report...{Colors.END}")
    print(f"{Colors.YELLOW}[!] Press Ctrl+C again to force quit.{Colors.END}")
    
    # Set up a more aggressive handler for second Ctrl+C
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(1))


def main():
    parser = argparse.ArgumentParser(
        description="Check URLs from sitemap.xml against new domain",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  nulb https://oldsite.com/sitemap.xml https://oldsite.com https://newsite.com
  nulb https://example.com/sitemap.xml https://example.com https://new-example.com
        """,
    )
    parser.add_argument("sitemap_url", help="URL to the sitemap.xml file")
    parser.add_argument(
        "old_root", help="Root URL of the old site (e.g., https://oldsite.com)"
    )
    parser.add_argument(
        "new_domain", help="Root domain of the new site (e.g., https://newsite.com)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.1,
        help="Delay between requests in seconds (default: 0.1)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for the report (default: print to console)",
    )
    parser.add_argument(
        "--skip-meta",
        action="store_true",
        help="Skip meta title and description comparison (check 404s only)",
    )

    args = parser.parse_args()

    # Validate domain formats
    if not args.old_root.startswith(("http://", "https://")):
        args.old_root = "https://" + args.old_root
    if not args.new_domain.startswith(("http://", "https://")):
        args.new_domain = "https://" + args.new_domain

    # Ensure old_root ends without trailing slash for consistent path extraction
    args.old_root = args.old_root.rstrip("/")

    print(f"Starting URL migration check...")
    print(f"Sitemap: {args.sitemap_url}")
    print(f"Old root: {args.old_root}")
    print(f"New domain: {args.new_domain}")
    print(f"Delay between requests: {args.delay}s")
    print("-" * 60)

    # Parse sitemap
    urls = parse_sitemap(args.sitemap_url)

    if not urls:
        print("No URLs found in sitemap")
        sys.exit(1)

    # Check each URL
    urls_404 = []
    meta_differences = []
    non_404_count = 0

    print(f"\nChecking {len(urls)} URLs...")

    # Set up signal handler for graceful Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    for i, url in enumerate(urls, 1):
        # Check if we've been interrupted
        if interrupted:
            print(f"{Colors.YELLOW}[!] Stopping at URL {i}/{len(urls)} due to interrupt.{Colors.END}")
            break
            
        # Use spinner for URL checking
        result = check_url_with_spinner(url, args.old_root, args.new_domain, i, len(urls), args.skip_meta)
        
        # Print result list
        print_result_list(result, i, len(urls), args.skip_meta)
        
        # Track results
        if result["is_404"]:
            urls_404.append(result)
        else:
            non_404_count += 1
            # Check for meta differences only if meta checking is enabled
            if not args.skip_meta and (not result["meta_matches"]["title"] or not result["meta_matches"]["description"]):
                meta_differences.append(result)

        # Add delay to be respectful to the server
        if args.delay > 0:
            time.sleep(args.delay)

    # Generate report with consistent formatting
    print(f"\n\n{Colors.BOLD}{'=' * 80}{Colors.END}")
    print(f"{Colors.BOLD}URL MIGRATION CHECK REPORT{Colors.END}")
    print(f"{Colors.BOLD}{'=' * 80}{Colors.END}")
    print(f"{Colors.BOLD}Generated:{Colors.END} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{Colors.BOLD}Sitemap:{Colors.END}   {args.sitemap_url}")
    print(f"{Colors.BOLD}Old root:{Colors.END}  {args.old_root}")
    print(f"{Colors.BOLD}New domain:{Colors.END} {args.new_domain}")
    print(f"\n{Colors.BOLD}SUMMARY{Colors.END}")
    print(f"{Colors.CYAN}{'-' * 80}{Colors.END}")
    print(f"{Colors.BOLD}Total URLs checked:{Colors.END} {len(urls)}")
    print(f"{Colors.BOLD}Non-404 responses:{Colors.END} {non_404_count}")
    print(f"{Colors.BOLD}404 responses:{Colors.END} {len(urls_404)}")
    print(f"{Colors.BOLD}Meta differences:{Colors.END} {len(meta_differences)}")

    # High Priority: 404 Errors
    if urls_404:
        print(f"\n{Colors.RED}{Colors.BOLD}HIGH PRIORITY: 404 ERRORS ({len(urls_404)} found){Colors.END}")
        print(f"{Colors.RED}{'=' * 80}{Colors.END}")
        
        for i, result in enumerate(urls_404, 1):
            print(f"\n{Colors.CYAN}{'-' * 80}{Colors.END}")
            print(f"{Colors.BOLD}[{i:03d}/{len(urls_404):03d}] 404 ERROR{Colors.END}")
            print(f"{Colors.BOLD}Original:{Colors.END} {result['original_url']}")
            print(f"{Colors.BOLD}New:{Colors.END}      {result['new_url']}")
            if result.get("final_url") and result.get("final_url") != result["new_url"]:
                print(f"{Colors.BOLD}Final:{Colors.END}    {result['final_url']}")
            print(f"{Colors.BOLD}Status:{Colors.END}   {Colors.RED}{result['status_code']}{Colors.END}")
    else:
        print(f"\n{Colors.GREEN}{Colors.BOLD}404 ERRORS: NONE FOUND{Colors.END}")
        print(f"{Colors.GREEN}{'=' * 80}{Colors.END}")
        print(f"{Colors.GREEN}SUCCESS: All URLs are accessible on the new domain!{Colors.END}")

    # Meta Differences (only show if meta checking was enabled)
    if not args.skip_meta:
        if meta_differences:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}META TITLE/DESCRIPTION DIFFERENCES ({len(meta_differences)} found){Colors.END}")
            print(f"{Colors.YELLOW}{'=' * 80}{Colors.END}")
            
            for i, result in enumerate(meta_differences, 1):
                print(f"\n{Colors.CYAN}{'-' * 80}{Colors.END}")
                print(f"{Colors.BOLD}[{i:03d}/{len(meta_differences):03d}] META DIFFERENCES{Colors.END}")
                print(f"{Colors.BOLD}Original:{Colors.END} {result['original_url']}")
                print(f"{Colors.BOLD}New:{Colors.END}      {result['new_url']}")
                if result.get("final_url") and result.get("final_url") != result["new_url"]:
                    print(f"{Colors.BOLD}Final:{Colors.END}    {result['final_url']}")
                
                if not result["meta_matches"]["title"]:
                    print(f"{Colors.BOLD}Title:{Colors.END}    {Colors.RED}DIFFERENT{Colors.END}")
                    orig_title = result["original_meta"]["title"] or "(none)"
                    new_title = result["new_meta"]["title"] or "(none)"
                    print(f"         Original: {Colors.MAGENTA}{orig_title}{Colors.END}")
                    print(f"         New:      {Colors.CYAN}{new_title}{Colors.END}")
                
                if not result["meta_matches"]["description"]:
                    print(f"{Colors.BOLD}Desc:{Colors.END}     {Colors.RED}DIFFERENT{Colors.END}")
                    orig_desc = result["original_meta"]["description"] or "(none)"
                    new_desc = result["new_meta"]["description"] or "(none)"
                    print(f"         Original: {Colors.MAGENTA}{orig_desc}{Colors.END}")
                    print(f"         New:      {Colors.CYAN}{new_desc}{Colors.END}")
        else:
            print(f"\n{Colors.GREEN}{Colors.BOLD}META DIFFERENCES: NONE FOUND{Colors.END}")
            print(f"{Colors.GREEN}{'=' * 80}{Colors.END}")
            print(f"{Colors.GREEN}SUCCESS: All meta titles and descriptions match!{Colors.END}")
    else:
        print(f"\n{Colors.BLUE}{Colors.BOLD}META CHECKING: SKIPPED{Colors.END}")
        print(f"{Colors.BLUE}{'=' * 80}{Colors.END}")
        print(f"{Colors.BLUE}Meta title and description comparison was disabled with --skip-meta{Colors.END}")

    # Build plain text report for file output
    report_lines = []
    report_lines.append("URL Migration Check Report")
    report_lines.append("=" * 80)
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Sitemap: {args.sitemap_url}")
    report_lines.append(f"Old root: {args.old_root}")
    report_lines.append(f"New domain: {args.new_domain}")
    report_lines.append("")
    report_lines.append("SUMMARY")
    report_lines.append("-" * 80)
    report_lines.append(f"Total URLs checked: {len(urls)}")
    report_lines.append(f"Non-404 responses: {non_404_count}")
    report_lines.append(f"404 responses: {len(urls_404)}")
    report_lines.append(f"Meta differences: {len(meta_differences)}")
    report_lines.append("")

    if urls_404:
        report_lines.append(f"HIGH PRIORITY: 404 ERRORS ({len(urls_404)} found)")
        report_lines.append("=" * 80)
        for i, result in enumerate(urls_404, 1):
            report_lines.append("")
            report_lines.append(f"[{i:03d}/{len(urls_404):03d}] 404 ERROR")
            report_lines.append(f"Original: {result['original_url']}")
            report_lines.append(f"New:      {result['new_url']}")
            if result.get("final_url") and result.get("final_url") != result["new_url"]:
                report_lines.append(f"Final:    {result['final_url']}")
            report_lines.append(f"Status:   {result['status_code']}")
    else:
        report_lines.append("404 ERRORS: NONE FOUND")
        report_lines.append("=" * 80)
        report_lines.append("SUCCESS: All URLs are accessible on the new domain!")

    report_lines.append("")
    if not args.skip_meta:
        if meta_differences:
            report_lines.append(f"META TITLE/DESCRIPTION DIFFERENCES ({len(meta_differences)} found)")
            report_lines.append("=" * 80)
            for i, result in enumerate(meta_differences, 1):
                report_lines.append("")
                report_lines.append(f"[{i:03d}/{len(meta_differences):03d}] META DIFFERENCES")
                report_lines.append(f"Original: {result['original_url']}")
                report_lines.append(f"New:      {result['new_url']}")
                if result.get("final_url") and result.get("final_url") != result["new_url"]:
                    report_lines.append(f"Final:    {result['final_url']}")
                
                if not result["meta_matches"]["title"]:
                    report_lines.append("Title:    DIFFERENT")
                    orig_title = result["original_meta"]["title"] or "(none)"
                    new_title = result["new_meta"]["title"] or "(none)"
                    report_lines.append(f"         Original: {orig_title}")
                    report_lines.append(f"         New:      {new_title}")
                
                if not result["meta_matches"]["description"]:
                    report_lines.append("Desc:     DIFFERENT")
                    orig_desc = result["original_meta"]["description"] or "(none)"
                    new_desc = result["new_meta"]["description"] or "(none)"
                    report_lines.append(f"         Original: {orig_desc}")
                    report_lines.append(f"         New:      {new_desc}")
        else:
            report_lines.append("META DIFFERENCES: NONE FOUND")
            report_lines.append("=" * 80)
            report_lines.append("SUCCESS: All meta titles and descriptions match!")
    else:
        report_lines.append("META CHECKING: SKIPPED")
        report_lines.append("=" * 80)
        report_lines.append("Meta title and description comparison was disabled with --skip-meta")

    report_text = "\n".join(report_lines)

    # Output report to file if specified
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(report_text)
            print(f"\n{Colors.BOLD}Report saved to:{Colors.END} {args.output}")
        except IOError as e:
            print(f"{Colors.RED}Error writing to file: {e}{Colors.END}")

    # Exit with error code if there were 404s
    if urls_404:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
