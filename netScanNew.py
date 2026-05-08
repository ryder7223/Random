import socket
import threading
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
import math
import sys
from typing import List, Tuple

# === Configuration ===
showProgress = False
showOverallProgress = True
saveToFile = False
maxWorkers = 10000
perIpWorker = 50
connectTimeout = 0.25
maxScanFull = 200000
sampleSeed = None

# === Globals ===
overallPbar = None
fileLock = threading.Lock()
progressLock = threading.Lock()
completedCount = 0


def printAboveProgress(message: str):
    if not saveToFile:
        if overallPbar:
            overallPbar.clear()
            print(message)
            overallPbar.refresh()
        else:
            print(message)


def scanPort(ip: str, port: int, timeout: float = connectTimeout):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        res = s.connect_ex((ip, port))
        if res == 0:
            if saveToFile:
                with fileLock:
                    with open("open_ips80.txt", "a") as f:
                        f.write(f"{ip}:{port}\n")
            else:
                printAboveProgress(f"[OPEN] {ip}:{port}")
    except Exception:
        pass
    finally:
        try:
            s.close()
        except Exception:
            pass


def scanIpPorts(ip: str, ports: List[int]):
    with ThreadPoolExecutor(max_workers=perIpWorker) as executor:
        futures = []
        if showProgress:
            with tqdm(ports, desc=f"Scanning {ip}", leave=False,
                      bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as portPbar:
                for port in ports:
                    futures.append(executor.submit(scanPort, ip, port))
                for future in as_completed(futures):
                    portPbar.update(1)
        else:
            for port in ports:
                futures.append(executor.submit(scanPort, ip, port))
            for future in as_completed(futures):
                pass


# -------------------------
# Parsing and interval utilities
# -------------------------
def clampInt(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def parseSinglePart(part: str) -> List[Tuple[int, int]]:
    part = part.strip()
    if not part:
        return []
    if '-' in part:
        a, b = part.split('-', 1)
        a = clampInt(int(a), 0, 255)
        b = clampInt(int(b), 0, 255)
        if a > b:
            a, b = b, a
        return [(a, b)]
    v = clampInt(int(part), 0, 255)
    return [(v, v)]


def mergeIntervals(intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    if not intervals:
        return []
    intervals = sorted(intervals)
    merged = []
    curS, curE = intervals[0]
    for s, e in intervals[1:]:
        if s <= curE + 1:
            curE = max(curE, e)
        else:
            merged.append((curS, curE))
            curS, curE = s, e
    merged.append((curS, curE))
    return merged


def parseOctetSpecToRanges(spec: str) -> List[Tuple[int, int]]:
    spec = spec.strip()
    if spec == "" or spec == "*":
        return [(0, 255)]

    parts = [p.strip() for p in spec.split(',') if p.strip() != ""]
    pos = []
    neg = []

    for p in parts:
        if p.startswith('!'):
            neg.extend(parseSinglePart(p[1:].strip()))
        else:
            pos.extend(parseSinglePart(p))

    if pos:
        pos = mergeIntervals(pos)
    else:
        pos = [(0, 255)]

    if not neg:
        return pos

    neg = mergeIntervals(neg)
    allowed = []

    for ps, pe in pos:
        cur = ps
        for ns, ne in neg:
            if ne < cur or ns > pe:
                continue
            if ns <= cur <= ne:
                cur = ne + 1
            elif cur < ns:
                allowed.append((cur, ns - 1))
                cur = ne + 1
            if cur > pe:
                break
        if cur <= pe:
            allowed.append((cur, pe))

    return mergeIntervals(allowed)


def octetRangesCount(ranges: List[Tuple[int, int]]) -> int:
    return sum((e - s + 1) for s, e in ranges)


def generateIpIteratorFromPattern(pattern: str):
    octets = pattern.split('.')
    while len(octets) < 4:
        octets.append('*')

    rangesPerOctet = []
    counts = []
    for oc in octets[:4]:
        r = parseOctetSpecToRanges(oc)
        rangesPerOctet.append(r)
        counts.append(octetRangesCount(r))

    total = 1
    for c in counts:
        total *= c

    return rangesPerOctet, counts, total


def sampleIpsFromRanges(rangesPerOctet: List[List[Tuple[int, int]]], sampleSize: int, seed=None):
    if seed is not None:
        random.seed(seed)

    out = set()
    attempts = 0
    limit = sampleSize * 5 + 1000

    while len(out) < sampleSize and attempts < limit:
        chosen = []
        for ranges in rangesPerOctet:
            total = sum((e - s + 1) for s, e in ranges)
            r = random.randint(0, total - 1)
            acc = 0
            val = None
            for s, e in ranges:
                ln = e - s + 1
                if acc + ln > r:
                    val = s + (r - acc)
                    break
                acc += ln
            if val is None:
                val = ranges[-1][1]
            chosen.append(str(val))

        out.add('.'.join(chosen))
        attempts += 1

    return list(out)


def iterIpsFromRanges(rangesPerOctet):
    rA, rB, rC, rD = rangesPerOctet
    for aS, aE in rA:
        for a in range(aS, aE + 1):
            for bS, bE in rB:
                for b in range(bS, bE + 1):
                    for cS, cE in rC:
                        for c in range(cS, cE + 1):
                            for dS, dE in rD:
                                for d in range(dS, dE + 1):
                                    yield f"{a}.{b}.{c}.{d}"


# -------------------------
# Random-IP generation with exclusion support
# -------------------------
def randomIpMatchesRanges(ip: str, rangesPerOctet) -> bool:
    parts = ip.split('.')
    if len(parts) != 4:
        return False
    for i in range(4):
        val = int(parts[i])
        valid = False
        for s, e in rangesPerOctet[i]:
            if s <= val <= e:
                valid = True
                break
        if not valid:
            return False
    return True


def generateRandomIpsWithExclusion(count: int, exclPattern: str):
    if exclPattern.strip() == "":
        return list({
            f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
            for _ in range(count * 2)
        })[:count]

    rangesPerOctet, _, total = generateIpIteratorFromPattern(exclPattern)

    out = set()
    attempts = 0
    hardLimit = count * 50

    while len(out) < count and attempts < hardLimit:
        ip = f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
        if randomIpMatchesRanges(ip, rangesPerOctet):
            out.add(ip)
        attempts += 1

    return list(out)


# -------------------------
# MAIN
# -------------------------
def main():
    global overallPbar, completedCount

    ipInput = input("Enter the IP address (supports exclusions, blank = random): ").strip()

    if ipInput == "":
        numIps = input("How many random IPs do you want to search? (default 256): ").strip()
        numIps = int(numIps) if numIps.isdigit() and int(numIps) > 0 else 256

        excl = input("Random IP exclusion pattern (optional, same syntax as normal patterns): ").strip()

        ipsToScan = generateRandomIpsWithExclusion(numIps, excl)
        totalIps = len(ipsToScan)
        sampling = False
    else:
        try:
            rangesPerOctet, counts, totalIps = generateIpIteratorFromPattern(ipInput)
        except Exception as e:
            print("Invalid input format:", e)
            return

        sampling = False
        if totalIps == 0:
            print("Pattern results in zero addresses.")
            return

        if totalIps > maxScanFull:
            sampleSize = maxScanFull
            print(f"Estimated total IPs = {totalIps:,}. Sampling {sampleSize:,} addresses.")
            ipsToScan = sampleIpsFromRanges(rangesPerOctet, sampleSize, seed=sampleSeed)
            totalIps = len(ipsToScan)
            sampling = True
        else:
            ipsToScan = iterIpsFromRanges(rangesPerOctet)

    portInput = input("Enter port or port range (e.g., 80 or 20-25): ").strip()
    if '-' in portInput:
        try:
            startPort, endPort = map(int, portInput.split('-', 1))
            ports = list(range(max(0, startPort), min(65535, endPort) + 1))
        except Exception:
            print("Invalid port range.")
            return
    else:
        try:
            ports = [int(portInput)]
        except Exception:
            print("Invalid port.")
            return

    workers = maxWorkers if maxWorkers <= 1000 else 1000
    completedCount = 0

    def taskDoneCallback(fut):
        global completedCount
        with progressLock:
            completedCount += 1
            if showOverallProgress and overallPbar:
                overallPbar.update(1)

    futures = []
    pendingSemaphore = threading.Semaphore(workers * 2)

    def submitIp(ipStr):
        pendingSemaphore.acquire()
        try:
            f = executor.submit(scanIpPorts, ipStr, ports)
            f.add_done_callback(lambda fut: (pendingSemaphore.release(), taskDoneCallback(fut)))
            futures.append(f)
        except Exception as e:
            pendingSemaphore.release()
            print("Submission error:", e)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        if showOverallProgress:
            overallPbar = tqdm(total=totalIps, desc="Overall Progress", leave=True, position=0)

        try:
            if isinstance(ipsToScan, list):
                for ip in ipsToScan:
                    submitIp(ip)
                for fut in as_completed(futures):
                    pass
            else:
                for ip in ipsToScan:
                    submitIp(ip)
                for fut in as_completed(futures):
                    pass
        except KeyboardInterrupt:
            print("Interrupted by user; shutting down.")
            executor.shutdown(wait=False)
            sys.exit(1)
        finally:
            if showOverallProgress and overallPbar:
                overallPbar.close()


if __name__ == "__main__":
    main()