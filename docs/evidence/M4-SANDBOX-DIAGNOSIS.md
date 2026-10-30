# Historical container diagnosis — superseded requirement

The user subsequently chose direct VM execution with no Codex sandbox.
[Native M4 acceptance is complete](M4-NATIVE.md); the original diagnosis below
is retained for history, not as a current blocker.

# M4 sandbox diagnosis — 2026-10-30

The first demonstrated blocker is Docker's default syscall policy rejecting the
namespace creation required by both Codex/bubblewrap and Chromium. The installed
Docker AppArmor default template also forbids mounts, which a replacement syscall
policy would not resolve by itself. No security policy was changed during diagnosis.
M4 remains incomplete. See [raw observations](m4-sandbox-diagnosis.json).

## Reproduction and observed results

The existing M4 image stayed at
`sha256:5cb0fed98f68ac5284b129c6090cd1c75d17f09583f2cb5789d25a6e2d4e3121`.
A separate runner-owned diagnostic image adds Debian strace 6.1 and libunwind8:
`sha256:feaada7b4a5fa704fa4440fd11be59a1ad386e2a75642c2f3a43215134ed485f`.
Its Dockerfile is [here](../../containers/m4/diagnostics/Dockerfile). Verify the local
base tag's image ID before building; Dockerfile `FROM sha256:<local image ID>` is
not a supported way to resolve a local image and initially attempted a registry
lookup. The corrected build uses the inspected local base tag. No registry
credentials were requested or changed.

Every probe retained non-root UID/GID 1000, zero effective capabilities,
no-new-privileges, read-only rootfs, enforced `docker-default` AppArmor, builtin
seccomp, no network, resource limits and automatic removal. There were **no host
mounts**: all inputs were fixed probe commands; HOME/scratch were ephemeral tmpfs.
No project, reference checkout, state namespace or credentials were supplied.

The JSON captures the complete Docker base argv and actual strace outputs.
Representative commands after that base argv:

```text
strace -f -e trace=clone,clone3,unshare,mount,setns,chroot,pivot_root,prctl,seccomp,execve bwrap --unshare-user --unshare-pid --unshare-net --ro-bind / / -- /bin/true
strace -f -e trace=clone,clone3,unshare,mount,setns,prctl chromium --headless --disable-gpu --dump-dom about:blank
```

Codex was traced with `codex sandbox --permission-profile :workspace -C /workspace
-- /bin/true`, after creating a private empty CODEX_HOME. This invoked no model.
Its helper made the following failing call:

```text
clone(..., flags=CLONE_NEWNS|CLONE_NEWIPC|CLONE_NEWUSER|CLONE_NEWPID|CLONE_NEWNET|SIGCHLD) = -1 EPERM
```

The standalone bubblewrap probe also failed at namespace clone, with IPC omitted
from that simpler invocation. Chromium's trace reached:

```text
clone(..., flags=CLONE_NEWUSER|SIGCHLD) = -1 EPERM
```

Ordinary process/thread clone calls succeeded. Chromium's clone3 calls returned
ENOSYS and successfully fell back to ordinary clone. That is compatible with the
profile's intended glibc fallback and is not evidence of an obsolete kernel.
Separate Python ctypes child probes reported EPERM for `unshare(0)`, user-only,
mount-only and combined user/mount unshare. Even the no-op being blocked strongly
corroborates syscall filtering rather than a namespace quota or missing kernel
feature. No probe relaxed its filter to force a success.

## Policy attribution

Reading Go build metadata from the installed `/usr/bin/dockerd` identified these
exact bundled modules, without running the daemon executable:

- `github.com/moby/profiles/seccomp v0.2.4`
- `github.com/moby/profiles/apparmor v0.2.2`

The matching upstream [seccomp v0.2.4 source](https://raw.githubusercontent.com/moby/profiles/seccomp/v0.2.4/seccomp/default.json)
defaults to EPERM. With CAP_SYS_ADMIN absent, its clone rule requires namespace
mask `0x7e020000` to be zero; both observed namespace requests violate that rule.
Its unshare/mount rules require CAP_SYS_ADMIN. This source rule plus the actual
trace identifies a sufficient first blocker. Exact installed BPF was not dumped,
so this is attribution from observed behavior and installed module/source evidence.

The matching [AppArmor v0.2.2 template](https://raw.githubusercontent.com/moby/profiles/apparmor/v0.2.2/apparmor/template.go)
includes `deny mount,`. Bubblewrap's planned sandbox builds a new filesystem view,
so a syscall-only adjustment would still encounter this restriction under that
template. This second failure has **not** been observed dynamically: namespace
creation fails first, and loaded kernel policy bytes were not inspected. Treat it
as a policy-source finding requiring confirmation, not a second successful probe.

`/etc/apparmor.d/bwrap-userns-restrict` exists on the host filesystem. Its presence
does not establish the active Docker policy or remove Docker's syscall filter.
The relevant Docker process reports `docker-default (enforce)`.

## Chromium and effective settings

The image has bubblewrap 0.8.0 and Chromium 156.0.8078.73. A package query confirms
`chromium-sandbox` is uninstalled, and `/usr/lib/chromium/chrome-sandbox` is absent.
Thus the failed user-namespace route has no installed setuid helper fallback.
Merely installing that helper is not an established solution: the required outer
no-new-privileges flag prevents setuid privilege elevation. The intended repair
should enable the constrained unprivileged namespace route and test actual browser
rendering with its sandbox retained.

Inside the Docker container, read-only settings were:

| Setting | Value |
| --- | --- |
| kernel.unprivileged_userns_clone | 1 |
| kernel.apparmor_restrict_unprivileged_userns | 1 |
| user.max_user_namespaces | 31437 |
| AppArmor | docker-default (enforce) |
| Effective capabilities | 0 |
| NoNewPrivs / Seccomp | 1 / 2 |

The earlier value 2147483647 came from the **tool session's** proc view. The Docker
probe sees 31437. Do not equate the tool sandbox's virtualized view with the daemon
container's effective namespace context. Both values are nonzero; this diagnosis
does not establish quota exhaustion.

Privileged journal/loaded-profile reads were unavailable because `sudo -n` requires
a password. The readable kern.log contains old host bubblewrap AppArmor denials at
04:15, not a correlated current Docker denial. They were not used to attribute the
current failure. Do not disclose a password or grant a privileged project container
to retrieve diagnostics.

## Next concrete work

Prepare runner-specific confined seccomp and AppArmor policies based on the
observed namespace/mount requirements. Preserve host defaults, global sysctls,
outer capability drops/no-new-privileges, read-only mounts, offline execution and
Codex/Chromium sandboxing. Avoid treating a generic namespace permission grant as
proof that the resulting boundary is safe. Any candidate profiles need review,
explicit configuration identity/hashes in approval, negative boundary tests and
actual nested-sandbox probes before adoption. The launcher currently hardcodes
default-profile names and would need a deliberate policy-schema update.

Loading a separately named AppArmor policy into the host kernel requires an
administrator-capable action; none was taken. Prepare exact install/unload and
rollback steps before applying it. A kernel/OS upgrade or replacement host has not
been demonstrated necessary. A policy fix may expose additional runtime issues,
so do not promise that two profile changes alone complete M4.

All diagnostic containers were automatically removed; an ancestor-filtered Docker
listing was empty. The diagnostic image/build cache remain local development
artifacts. Original M4 files were preserved; no service, daemon configuration,
credential, operational state, reference checkout or publication was changed.
