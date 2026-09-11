# Installation

How much you install depends on what you want to do.

| You want to | Install |
| --- | --- |
| Build a k-mesh ladder, label convergence, read a published record | [the package](package.md) |
| Publish a dataset to PSDI | the package with the `publish` extra |
| Run the calculations yourself | the package, then AiiDA, then Quantum ESPRESSO |

Only the last one needs the full stack, and it has two further stages:

1. install AiiDA and its local services on macOS;
2. add the Quantum ESPRESSO plugin, SCARF computer, `pw.x` code, and
   pseudopotentials.

Keep the complete QE workflow in one dedicated Python environment. Put other
AiiDA workflow stacks in separate environments when their version constraints
conflict.

## Choose the next page

[Install goldilocks-data](package.md){ .md-button .md-button--primary }
[Install AiiDA on macOS](aiida-macos.md){ .md-button }
[Add Quantum ESPRESSO and SCARF](qe-scarf.md){ .md-button }
