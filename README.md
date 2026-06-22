# certcheck

A tiny, dependency-light TLS certificate expiry checker. Point it at a list of
hosts; it connects, reads each server's leaf certificate, and reports the common
name, SANs, issuer, and days-to-expiry. The process exit code reflects the worst
status found, so it drops cleanly into cron, a systemd timer, or CI.

It intentionally does **not** validate trust — the goal is expiry/identity
visibility, so self-signed certs and internal CAs report just like public ones.

## Install

```bash
pip install .
# or just run the single file:
pip install cryptography
python certcheck.py example.com
```

Python 3.10+. The only third-party dependency is
[`cryptography`](https://pypi.org/project/cryptography/).

## Windows

### GUI (no command line, no Python)

For a point-and-click tool, build the GUI executable:

```powershell
.\build.ps1                 # produces dist\certcheck.exe and dist\certcheck-gui.exe
.\dist\certcheck-gui.exe    # or just double-click it
```

`certcheck-gui.exe` is fully self-contained (~24 MB, bundles Python + Tk + the deps).
Double-click it, paste your hosts (one per line), click **Scan**, and read the colour-coded
results. It **remembers your host list and thresholds** between runs (saved to
`%APPDATA%\certcheck\config.json`) and exports the results to an **Excel (.xlsx)** workbook
with one button. Nothing to install — hand the single `.exe` to whoever needs it.

### Command line

Three ways to run the CLI, in order of "least Python ceremony":

1. **Standalone `certcheck.exe` (no Python needed)** — built alongside the GUI by `build.ps1`:

   ```powershell
   .\dist\certcheck.exe example.com google.com
   ```

   Drop it anywhere — a server, a USB stick, a Task Scheduler action — no runtime install.

2. **`certcheck.cmd` from source.** Put this folder on your `PATH` and call `certcheck`
   directly from `cmd` or PowerShell (uses your installed Python):

   ```powershell
   certcheck example.com --warn 45
   ```

3. **`pip install .`** — creates a `certcheck.exe` shim in your Python `Scripts\` directory.
   (`pip install .[gui]` also pulls in `openpyxl` for the GUI's Excel export.)

Exit codes propagate, so the CLI works in Task Scheduler / CI the same as on Linux. ANSI color
auto-disables when output isn't a console (or set `NO_COLOR`).

## Usage

```bash
certcheck example.com google.com:443
certcheck --file hosts.txt --warn 45 --crit 10
certcheck example.com --json
```

`hosts.txt` is one `host[:port]` per line; `#` comments and blank lines are ignored.

### Options

| Flag | Default | Meaning |
|------|---------|---------|
| `-w, --warn N` | 30 | warn when a cert expires in ≤ N days |
| `-c, --crit N` | 7 | critical when a cert expires in ≤ N days |
| `-t, --timeout S` | 5 | per-host connection timeout (seconds) |
| `-f, --file PATH` | — | read targets from a file |
| `--json` | — | emit JSON instead of the table |
| `--color auto\|always\|never` | auto | colorize the table (respects `NO_COLOR`) |

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | all certificates OK |
| 1 | at least one WARNING (expiring soon) |
| 2 | at least one CRITICAL (expired, imminent, or host unreachable) |
| 3 | usage error (no targets) |

Example cron line that emails you only when something needs attention:

```cron
0 7 * * *  certcheck --file /etc/certcheck/hosts.txt || mail -s "cert check" you@example.com
```

## Example output

```
  CRIT  oldbox.internal:443     -3d  oldbox.internal  (Internal CA)
  WARN  example.com:443         21d  example.com  (R3)
  OK    google.com:443          68d  *.google.com  (Google Trust Services)
```

## Library use

```python
from certcheck import check_cert, check_many, Status

r = check_cert("example.com", 443, warn_days=30, crit_days=7)
print(r.cn, r.days_remaining, Status(r.status).name)
```

## License

MIT — see [LICENSE](LICENSE).
