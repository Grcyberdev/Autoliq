#!/usr/bin/env python3
"""
Dynamic Indian Proxy Discovery & Pre-Flight Validator
Finds and verifies working Indian HTTP/HTTPS proxies that can reach the Assam Excise portal.
"""

import sys
import os
import time
import ssl
import urllib.request
import concurrent.futures

PORTAL_URL = "https://stateexcise.assam.gov.in/index.php/site/login"

PROXY_SOURCES = [
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/IN/data.txt",
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=8000&country=IN&ssl=all&anonymity=all",
]

def check_direct_connectivity():
    print("🔍 Testing direct connectivity to Assam Excise portal...")
    req = urllib.request.Request(
        PORTAL_URL,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    ctx = ssl._create_unverified_context()
    try:
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            if resp.status == 200:
                print(f"✅ Direct connection to portal succeeded ({time.time() - t0:.2f}s)! No proxy needed.")
                return True
    except Exception as e:
        print(f"⚠️ Direct connection timed out / dropped: {e}")
    return False

def fetch_candidate_proxies():
    candidates = []
    seen = set()
    print("📥 Fetching public Indian proxy candidates...")
    ctx = ssl._create_unverified_context()

    for src in PROXY_SOURCES:
        try:
            req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6, context=ctx) as r:
                text = r.read().decode("utf-8", errors="ignore")
                for line in text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    # Normalize proxy string (accept http://ip:port or ip:port)
                    cleaned = line.replace("https://", "").split()[0].split(",")[0]
                    if not cleaned.startswith("http://") and not cleaned.startswith("socks"):
                        cleaned = f"http://{cleaned}"
                    # We focus on HTTP/HTTPS proxies for Selenium Chrome stability
                    if cleaned.startswith("http://"):
                        host_port = cleaned.replace("http://", "")
                        parts = host_port.split(":")
                        if len(parts) == 2 and parts[0].count(".") == 3 and parts[1].isdigit():
                            if cleaned not in seen:
                                seen.add(cleaned)
                                candidates.append(cleaned)
        except Exception as e:
            print(f"   ⚠️ Source {src} fetch warning: {e}")

    print(f"📊 Collected {len(candidates)} Indian HTTP proxy candidates to test.")
    return candidates

def verify_single_proxy(proxy_url):
    handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
    ctx = ssl._create_unverified_context()
    opener = urllib.request.build_opener(handler)
    req = urllib.request.Request(
        PORTAL_URL,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    t0 = time.time()
    try:
        with opener.open(req, timeout=4) as resp:
            elapsed = time.time() - t0
            if resp.status == 200:
                body = resp.read(1024).decode("utf-8", errors="ignore").lower()
                if "assam" in body or "excise" in body or "login" in body or "<!doctype" in body or "<html" in body:
                    return (proxy_url, elapsed)
    except Exception:
        pass
    return None

def find_working_indian_proxy(max_candidates=60, max_workers=25):
    candidates = fetch_candidate_proxies()
    if not candidates:
        print("❌ Could not retrieve any proxy candidates.")
        return None

    test_batch = candidates[:max_candidates]
    print(f"⚡ Concurrently testing {len(test_batch)} Indian proxies against portal (timeout=4s)...")
    
    verified = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(verify_single_proxy, p) for p in test_batch]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                proxy_url, latency = res
                print(f"   🎯 Live Indian Proxy verified: {proxy_url} (latency: {latency:.2f}s)")
                verified.append(res)
                # If we found at least 2 fast proxies, break early to save startup time
                if len(verified) >= 2:
                    # Cancel remaining futures
                    for f in futures:
                        f.cancel()
                    break

    if verified:
        verified.sort(key=lambda x: x[1])
        best_proxy, best_time = verified[0]
        print(f"🏆 Best Indian proxy selected: {best_proxy} (latency: {best_time:.2f}s)")
        return best_proxy

    print("⚠️ No verified live proxies found in this batch.")
    return None

def main():
    github_env = os.environ.get("GITHUB_ENV")

    # 1. Test direct connectivity first (if unblocked, use direct for max performance)
    if check_direct_connectivity():
        if github_env:
            with open(github_env, "a") as f:
                f.write("USE_INDIAN_PROXY=false\n")
                f.write("USE_TOR_PROXY=false\n")
        print("ℹ️ Configured workflow for direct connection.")
        return 0

    # 2. Find verified live Indian proxy
    proxy = find_working_indian_proxy()
    if proxy:
        if github_env:
            with open(github_env, "a") as f:
                f.write(f"INDIAN_PROXY={proxy}\n")
                f.write("USE_INDIAN_PROXY=true\n")
                f.write("USE_TOR_PROXY=false\n")
        print(f"✅ Successfully exported Indian proxy: {proxy}")
        return 0
    else:
        print("❌ Failed to find a live Indian proxy. Workflow will fail cleanly.")
        if github_env:
            with open(github_env, "a") as f:
                f.write("USE_INDIAN_PROXY=false\n")
                f.write("USE_TOR_PROXY=false\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
