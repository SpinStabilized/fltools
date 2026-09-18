<!-- Improved compatibility of back to top link: See: https://github.com/othneildrew/Best-README-Template/pull/73 -->
<a id="readme-top"></a>

<!--
*** This README follows the Best-README-Template by othneildrew:
*** https://github.com/othneildrew/Best-README-Template
-->



<!-- PROJECT SHIELDS -->
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]



<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/SpinStabilized/fltools">
    <img src="images/fltools_logo.png" alt="Logo" width=512>
  </a>

<h3 align="center">fltools</h3>

  <p align="center">
    Extra macro tools for FLDigi: push the selected logbook entry to QRZ or Club Log, and pull local weather onto the air, all from an <code>&lt;EXEC&gt;</code> macro key.
    <br />
    <a href="https://github.com/SpinStabilized/fltools"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/SpinStabilized/fltools/issues/new?labels=bug">Report Bug</a>
    &middot;
    <a href="https://github.com/SpinStabilized/fltools/issues/new?labels=enhancement">Request Feature</a>
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
        <li><a href="#configuration">Configuration</a></li>
      </ul>
    </li>
    <li>
      <a href="#usage">Usage</a>
      <ul>
        <li><a href="#fltools-qrz">fltools qrz</a></li>
        <li><a href="#fltools-clublog">fltools clublog</a></li>
        <li><a href="#fltools-wx">fltools wx</a></li>
        <li><a href="#exit-codes">Exit Codes</a></li>
        <li><a href="#field-mapping">Field Mapping</a></li>
        <li><a href="#logging">Logging</a></li>
        <li><a href="#troubleshooting">Troubleshooting</a></li>
      </ul>
    </li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>


> [!IMPORTANT]
> This is all very much still alpha testing level. Might be useful to others,
> definitely useful to me.

<!-- ABOUT THE PROJECT -->
## About The Project

FLDigi can hand off to an external program with the `<EXEC>` macro tag, and when
it does, it exports the station's state and the currently selected logbook entry
into the child process as `FLDIGI_*` environment variables. `fltools` is a small
Python CLI that sits on the other end of that handoff.

It gives you three things on macro keys:

* **`qrz`** uploads the selected logbook entry to your [QRZ Logbook][qrz-url] as a
  single ADIF record.
* **`clublog`** uploads that same entry to [Club Log][clublog-url] through the
  real-time API, with a lockout guard so that bad credentials cannot get your IP
  address firewalled.
* **`wx`** fetches current conditions and active alerts from
  [Pirate Weather][pw-url] for your Maidenhead grid square and prints a compact
  block straight into the transmit buffer.

Everything runs as one entry point, `fltools`, with a subcommand per job. A small
bash shim handles the awkward part of being launched by FLDigi (no login shell,
no useful `PATH`, and a stdout stream that goes out over the air).

<p align="right">(<a href="#readme-top">back to top</a>)</p>



### Built With

* [![Python][Python-shield]][Python-url]
* [![uv][uv-shield]][uv-url]
* [Requests][requests-url]
* [python-dotenv][dotenv-url]
* [maidenhead][maidenhead-url]

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- GETTING STARTED -->
## Getting Started

### Prerequisites

* **FLDigi**, with macro editing available (Configure > Macros).
* **Python 3.14 or later.** The version is pinned in `.python-version` and
  enforced by `pyproject.toml`. `uv` will fetch it for you if you do not have it.
* **[uv][uv-url]** for dependency management and running the tool.
* **Credentials for whichever subcommands you plan to use:**
  * QRZ: an XML Logbook Data subscription, then your key from
    **Logbook Data > Logbook Settings > API Key**.
  * Club Log: an account, an [API key][clublog-api-url], and an Application
    Password (not your account password).
  * Pirate Weather: a free [API key][pw-url].

### Installation

1. Clone the repo.
   ```sh
   git clone https://github.com/SpinStabilized/fltools.git
   cd fltools
   ```

2. Sync the environment.
   ```sh
   uv sync
   ```

3. Create your `.env` from the example and fill it in.
   ```sh
   cp .example_env .env
   ```
   > **Note:** `.env` grants write access to your logbooks. It is already in
   > `.gitignore`. Keep it that way.

4. Install the launcher shim into FLDigi's script directory. FLDigi prepends
   `~/.fldigi/scripts` to `PATH` for `<EXEC>` children, so this is what lets a
   macro simply say `fltools qrz`.
   ```sh
   cp utilities/fltools ~/.fldigi/scripts/fltools
   chmod +x ~/.fldigi/scripts/fltools
   ```

5. Edit the two paths at the top of `~/.fldigi/scripts/fltools` to match your
   machine.
   ```sh
   PROJECT_DIR=$HOME/source/fltools   # where you cloned this repo
   UV_BIN=/opt/homebrew/bin/uv        # output of `which uv`
   ```
   The default `UV_BIN` is the Homebrew path on Apple Silicon. On most Linux
   installs it will be `$HOME/.local/bin/uv` instead.

6. Add a macro in FLDigi (Configure > Macros) for each subcommand you want on a
   key.
   ```
   <EXEC>fltools qrz</EXEC>
   ```

<p align="right">(<a href="#readme-top">back to top</a>)</p>



### Configuration

All configuration lives in a `.env` file in the project root, beside
`pyproject.toml`. It is read at startup by every subcommand.

| Variable             | Used by   | Description                                                                        |
|----------------------|-----------|------------------------------------------------------------------------------------|
| `QRZ_KEY`            | `qrz`     | QRZ Logbook API key. Required.                                                     |
| `CLUBLOG_EMAIL`      | `clublog` | The email address on your Club Log account. Required.                              |
| `CLUBLOG_PASSWORD`   | `clublog` | Club Log Application Password. Required.                                           |
| `CLUBLOG_API_KEY`    | `clublog` | Club Log API key. Required.                                                        |
| `FLTOOLS_CALL`       | `clublog` | Station callsign the QSO is logged under. Falls back to FLDigi's `FLDIGI_MY_CALL`. |
| `FLTOOLS_PW_API_KEY` | `wx`      | Pirate Weather API key. Required.                                                  |
| `FLTOOLS_PW_UNITS`   | `wx`      | Unit system: `us`, `si`, `ca`, `uk`, or `uk2`. Defaults to `us`.                   |

`.example_env` lists every one of these with empty values, so copying it is the
fastest way to get a valid starting file.

Your grid square is not configured here. `wx` takes it from FLDigi's
`FLDIGI_MY_LOCATOR`, and falls back to a hardcoded default near Ellicott City,
Maryland if FLDigi does not supply one.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- USAGE EXAMPLES -->
## Usage

Once the shim is installed, every subcommand is reachable from a macro or from
your shell.

```sh
fltools qrz        # upload selected logbook entry to QRZ
fltools clublog    # upload selected logbook entry to Club Log
fltools wx         # print current conditions and alerts
fltools --help
```

Run straight from the repo without the shim:

```sh
uv run src/fltools.py wx
```

One thing to know before putting these on keys: FLDigi captures the child
process's **stdout and appends it to the transmit buffer**, re-parsing it for
macro tags. `wx` uses that deliberately. `qrz` and `clublog` print nothing at
all and report through the log file instead, so a failed upload will never put
noise on the air.

### fltools qrz

Reads the `FLDIGI_LOGBOOK_*` variables for the selected entry, builds one ADIF
record, and submits it to the QRZ Logbook API with `ACTION=INSERT` and
`OPTION=REPLACE`.

```
<EXEC>fltools qrz</EXEC>
```

`call`, `qso_date`, `time_on`, `band`, and `mode` are required by QRZ. If any of
them are blank in the selected entry, nothing is sent.

**Workflow:** log the QSO as usual, select the entry in the FLDigi logbook, then
press the macro key.

### fltools clublog

Same input, submitted to Club Log's `realtime.php` endpoint. This endpoint is
for one QSO at a time. Do not loop it over a backlog, or the IP address gets
throttled. Use Club Log's `putlogs.php` with an ADIF file for catch-up uploads.

```
<EXEC>fltools clublog</EXEC>
```

**The lockout.** FLDigi spawns a fresh process per macro press, so one run has no
way to warn the next. If Club Log rejects the credentials, `fltools` writes
`clublog_lockout.txt` into `src/` and refuses to send again until you delete it.
This exists because repeated failed authentications will get your IP address
firewalled by Club Log automatically. Fix the credentials in `.env`, delete the
file, carry on.

### fltools wx

Pulls the `currently` and `alerts` blocks from Pirate Weather for your grid
square and prints a single pipe-separated line, plus an alerts line when
something is active.

```
<EXEC>fltools wx</EXEC>
```

Sample output:

```
WX | Partly Cloudy | Temp 68F (feels 70F) | Humidity 64% | Wind 7mph WNW
ALERTS: [SEVERE] Severe Thunderstorm Watch
```

Because this one writes to stdout, the text lands in your transmit buffer ready
to send.

### Exit Codes

Every subcommand runs inside the same `fltools` process, so what follows is the
code your shell (or any wrapper script) actually sees. FLDigi throws it away,
which is why the log file matters more than this table in day to day use.

| Code | Meaning                                                                       | Set by           |
|------|-------------------------------------------------------------------------------|------------------|
| 0    | Work completed.                                                               | all              |
| 1    | Aborted before sending, or the far end rejected the record.                   | `qrz`, `clublog` |
| 2    | Transient failure: network error or HTTP 500. Safe to retry.                  | `clublog`        |
| 3    | Authentication failure, or an active lockout. Do not retry until it is fixed. | `clublog`        |

The subcommands do not yet use this range evenly. `clublog` distinguishes all
four cases. `qrz` collapses every failure into 1, whether that was a missing key,
a blank required field, or a rejection from QRZ. `wx` sets nothing at all, so it
returns 0 even when the weather fetch fails and it prints an empty line. Bringing
the three into line is on the [Roadmap](#roadmap).

One collision to know about: `argparse` exits with 2 on a usage error, such as an
unknown subcommand, which overlaps with `clublog`'s retry code.

### Field Mapping

Both upload subcommands map FLDigi's exported variables to ADIF fields as
follows. Blank fields are omitted from the record rather than sent empty, and
`time_on` / `time_off` have their colons stripped to satisfy ADIF.

| FLDigi variable               | ADIF field     |
|-------------------------------|----------------|
| `FLDIGI_LOGBOOK_ARRL_SECT_IN` | `arrl_sect`    |
| `FLDIGI_LOGBOOK_BAND`         | `band`         |
| `FLDIGI_LOGBOOK_CALL`         | `call`         |
| `FLDIGI_LOGBOOK_CLASS_IN`     | `class`        |
| `FLDIGI_LOGBOOK_CONTINENT`    | `cont`         |
| `FLDIGI_LOGBOOK_COUNTRY`      | `country`      |
| `FLDIGI_LOGBOOK_COUNTY`       | `cnty`         |
| `FLDIGI_LOGBOOK_CQZ`          | `cqz`          |
| `FLDIGI_LOGBOOK_DATE`         | `qso_date`     |
| `FLDIGI_LOGBOOK_DATE_OFF`     | `qso_date_off` |
| `FLDIGI_LOGBOOK_DXCC`         | `dxcc`         |
| `FLDIGI_LOGBOOK_FREQUENCY`    | `freq`         |
| `FLDIGI_LOGBOOK_IOTA`         | `iota`         |
| `FLDIGI_LOGBOOK_ITUZ`         | `ituz`         |
| `FLDIGI_LOGBOOK_LOCATOR`      | `gridsquare`   |
| `FLDIGI_LOGBOOK_MODE`         | `mode`         |
| `FLDIGI_LOGBOOK_NAME`         | `name`         |
| `FLDIGI_LOGBOOK_NOTES`        | `notes`        |
| `FLDIGI_LOGBOOK_QSL_VIA`      | `qsl_via`      |
| `FLDIGI_LOGBOOK_QTH`          | `qth`          |
| `FLDIGI_LOGBOOK_RST_IN`       | `rst_rcvd`     |
| `FLDIGI_LOGBOOK_RST_OUT`      | `rst_sent`     |
| `FLDIGI_LOGBOOK_SERNO_IN`     | `srx`          |
| `FLDIGI_LOGBOOK_SERNO_OUT`    | `stx`          |
| `FLDIGI_LOGBOOK_STATE`        | `state`        |
| `FLDIGI_LOGBOOK_TIME_OFF`     | `time_off`     |
| `FLDIGI_LOGBOOK_TIME_ON`      | `time_on`      |
| `FLDIGI_LOGBOOK_TX_PWR`       | `tx_pwr`       |
| `FLDIGI_LOGBOOK_VE_PROV`      | `ve_prov`      |

### Logging

Two files, both under `logs/` in the project root:

| File                   | Written by     | Contents                                             |
|------------------------|----------------|------------------------------------------------------|
| `logs/fltools.log`     | the Python CLI | Success and failure of each run, plus API responses. |
| `logs/fltools.err.log` | the bash shim  | stderr from `uv` and any Python traceback.           |

`fltools.log` rotates at roughly 1 MB and keeps 3 older copies. The default level
is `INFO`. For the full ADIF record sent upstream, pass `logging.DEBUG` to
`utils.fltools_logger_config()` in `src/fltools.py`.

Since macro output is invisible by design, tailing the log is the way to watch a
QSO go up:

```sh
tail -f logs/fltools.log
```

### Troubleshooting

**`uv: command not found` in `fltools.err.log`**
The `<EXEC>` child does not get a login or interactive shell, so it never sources
your `.bashrc` or `.profile` and `uv` may not be on `PATH` even though it works
fine in your terminal. This is exactly what `UV_BIN` in the shim is for. Set it
to the output of `which uv`.

**Nothing at all happens when I press the key**
Confirm the shim is executable and that FLDigi sees it. It should appear in the
macro editor's exec-script list. Then check `logs/fltools.err.log`.

**`QRZ_KEY is not set (check .env).`**
`.env` is missing, or it is not in the project root next to `pyproject.toml`.
The shim's `PROJECT_DIR` has to point at the clone for the file to be found.

**`Aborting upload: missing required field(s): ...`**
One of `call`, `qso_date`, `time_on`, `band`, or `mode` was empty in the selected
FLDigi entry. Fill it in and press the key again.

**`QSO upload failed: {'RESULT': 'FAIL', 'REASON': ...}`**
QRZ rejected the record. The `REASON` text in `logs/fltools.log` usually says
why: an invalid or expired key, a logbook not enabled for API access, or a
duplicate contact.

**`Upload blocked: lockout in place ...`**
Club Log rejected your credentials on an earlier run. Fix them in `.env`, delete
`src/clublog_lockout.txt`, then try again.

**Weather comes back empty or wrong location**
`wx` needs `FLDIGI_MY_LOCATOR`, which means your grid square has to be set in
FLDigi under Configure > Operator. Without it the tool falls back to a default
location in Maryland.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- ROADMAP -->
## Roadmap

The near-term theme is consistency. The three subcommands grew out of three
standalone scripts, and they still behave like it. Everything below is about
making `fltools` one tool rather than three under a shared launcher.

- [ ] Give every subcommand the same exit code contract, so 0/1/2/3 mean the same
      thing whichever one you called
- [ ] Bring `qrz` and `clublog` to parity: shared ADIF helpers, the same
      credential and required-field validation, and equivalent protection against
      hammering an API that has already said no
- [ ] Give `wx` a failure path, so a dead API key or an unreachable Pirate Weather
      is reported rather than printing an empty line and returning 0
- [ ] Replace the `sys.exit()` calls with graceful failure handling, so a run
      stands down cleanly instead of dropping out mid-flight
- [ ] Sort out the collision with `argparse`'s usage exit code of 2
- [ ] Use `flenv.get_env()` in `qrz.py` so a logbook field FLDigi does not export
      returns empty instead of raising `KeyError`
- [ ] Rename `QRZ_REQUIRED_ADIF_FIELDS`, now that `clublog` validates against it
      too
- [ ] Fill in project metadata in `pyproject.toml` (name, description)
- [ ] Add a `--version` flag
- [ ] Package properly so `uv tool install` can replace the bash shim

See the [open issues](https://github.com/SpinStabilized/fltools/issues) for a
full list of proposed features and known issues.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to
learn, inspire, and create. Any contributions you make are **greatly
appreciated**.

If you have a suggestion that would make this better, please fork the repo and
create a pull request. You can also simply open an issue with the tag
"enhancement". Don't forget to give the project a star. Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Top contributors:

<a href="https://github.com/SpinStabilized/fltools/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=SpinStabilized/fltools" alt="contrib.rocks image" />
</a>



<!-- LICENSE -->
## License

Distributed under the MIT License. See `LICENSE` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTACT -->
## Contact

Brian McLaughlin, N3BMC - n3bmc@arrl.net

Project Link: [https://github.com/SpinStabilized/fltools](https://github.com/SpinStabilized/fltools)

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

* [FLDigi and the `<EXEC>` macro](https://www.w1hkj.org/)
* [QRZ Logbook API](https://www.qrz.com/page/logbook30.html)
* [Club Log real-time API](https://clublog.freshdesk.com/support/solutions/articles/3000068746-api-keys)
* [Pirate Weather](https://pirateweather.net/)
* [maidenhead](https://github.com/space-physics/maidenhead) for grid square conversion
* [Best-README-Template](https://github.com/othneildrew/Best-README-Template)

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- MARKDOWN LINKS & IMAGES -->
[contributors-shield]: https://img.shields.io/github/contributors/SpinStabilized/fltools.svg?style=for-the-badge
[contributors-url]: https://github.com/SpinStabilized/fltools/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/SpinStabilized/fltools.svg?style=for-the-badge
[forks-url]: https://github.com/SpinStabilized/fltools/network/members
[stars-shield]: https://img.shields.io/github/stars/SpinStabilized/fltools.svg?style=for-the-badge
[stars-url]: https://github.com/SpinStabilized/fltools/stargazers
[issues-shield]: https://img.shields.io/github/issues/SpinStabilized/fltools.svg?style=for-the-badge
[issues-url]: https://github.com/SpinStabilized/fltools/issues
[license-shield]: https://img.shields.io/github/license/SpinStabilized/fltools.svg?style=for-the-badge
[license-url]: https://github.com/SpinStabilized/fltools/blob/main/LICENSE
[Python-shield]: https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54
[Python-url]: https://www.python.org/
[uv-shield]: https://img.shields.io/badge/uv-DE5FE9?style=for-the-badge&logo=uv&logoColor=white
[uv-url]: https://docs.astral.sh/uv/
[requests-url]: https://requests.readthedocs.io/
[dotenv-url]: https://github.com/theskumar/python-dotenv
[maidenhead-url]: https://github.com/space-physics/maidenhead
[qrz-url]: https://www.qrz.com/
[clublog-url]: https://clublog.org/
[clublog-api-url]: https://clublog.freshdesk.com/support/solutions/articles/3000068746-api-keys
[pw-url]: https://pirateweather.net/