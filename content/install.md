+++
title = "Install Camp"
description = "Install instructions and current source-build guidance for Camp."
weight = 10
+++

# Install Camp

Camp preview builds are distributed as GitHub Release archives. The installer
script detects your platform, downloads the matching archive, verifies its
checksum, and installs the Camp tools into your user profile.

## macOS and Linux

<div class="command-copy">
	<pre><code>curl -fsSL https://raw.githubusercontent.com/camplang-dev/camp/master/install.sh | sh</code></pre>
	<button type="button" data-copy="curl -fsSL https://raw.githubusercontent.com/camplang-dev/camp/master/install.sh | sh" aria-label="Copy command">
		<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="10" height="10" rx="2"></rect><path d="M5 15V7a2 2 0 0 1 2-2h8"></path></svg>
	</button>
</div>

The default install location is `~/.camp`. The script prints PATH instructions
after installation. To let it update a recognized shell profile, pass
`--add-to-path`.

## Windows

<div class="command-copy">
	<pre><code>irm https://raw.githubusercontent.com/camplang-dev/camp/master/install.ps1 | iex</code></pre>
	<button type="button" data-copy="irm https://raw.githubusercontent.com/camplang-dev/camp/master/install.ps1 | iex" aria-label="Copy command">
		<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="10" height="10" rx="2"></rect><path d="M5 15V7a2 2 0 0 1 2-2h8"></path></svg>
	</button>
</div>

The default install location is `%LOCALAPPDATA%\Camp`. Run the script from a
normal, non-admin PowerShell session. To update the user PATH automatically, run
the saved script with `-AddToPath`.

## Native compiler prerequisites

Camp lowers to C-compatible native output, so building or running Camp programs
requires a native C toolchain for the target you choose.

- Windows MSVC targets require Visual Studio Build Tools with the Desktop
  development with C++ workload. Camp finds the tools automatically when it can.
- macOS targets use Clang from Apple's command line developer tools:

  ```sh
  xcode-select --install
  ```

- Linux targets use GCC and the normal C development files. On Debian and
  Ubuntu:

  ```sh
  sudo apt install build-essential
  ```

Camp itself does not require .NET when installed from a release archive.

## Manual archives

Manual release archives are available from the compiler repository:

```text
https://github.com/camplang-dev/camp/releases
```

Preview releases include host tool distributions for Windows x64, Windows x86,
Linux x64, macOS Intel, and macOS Apple Silicon. Linux x86 is a generated-code
target, not a host tool distribution.

## Package managers

Package manager distribution is planned after the first preview release.

## Build from source

Compiler contributors can build Camp from source with the .NET 10 SDK:

```sh
git clone https://github.com/camplang-dev/camp.git
cd camp
dotnet build src/camplang.sln
```

After building, the compiler entry point is available from the repository's
`bin` directory.
