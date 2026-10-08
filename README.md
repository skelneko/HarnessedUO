# HarnessedUO

An independent fork of [ClassicUO](https://github.com/ClassicUO/ClassicUO) (BSD-2-Clause); changes are not contributed back. Architecture inspired by [Navrey](https://github.com/johnpwrs/navrey) ('Claude plays UO'). Developed against [ModernUO](https://github.com/modernuo/ModernUO) (GPL-3.0, not included). Ultima Online is a trademark of Electronic Arts; not affiliated. For your own dev shard, or privately-run shards whose rules allow automation; never official servers.

## What this is

A side project for myself to learn what a harness product could be.

HarnessedUO is an AI-agent harness for Ultima Online, built into the ClassicUO client: an in-process engine (`src/ClassicUO.Client/Harness/`) plus a Python agent service (`huo/`) that plays tasks you give it in game, using local models (LM Studio or Ollama) or Claude.

Status: early setup (phase P0). Not usable yet. A personal, non-commercial project.

## Where it may be used

- Your own dev shard, or privately-run shards whose rules allow automation. On shards you don't run, attended play only.
- Never official Ultima Online servers. ClassicUO's README: "Using a custom client to connect to official UO servers is strictly forbidden."
- No game assets are included. You need a legally obtained copy of the Ultima Online Classic client.

## Licence

- ClassicUO's code: BSD-2-Clause, see `LICENSE.md` (ClassicUO's, kept unchanged).
- Our additions (`huo/`, `src/ClassicUO.Client/Harness/`): BSD-2-Clause, see `huo/LICENSE`.
- Our edits inside ClassicUO's files are marked `// HUO:`; `git grep "HUO:"` lists them.
- ModernUO (GPL-3.0) is not included.
