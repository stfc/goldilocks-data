# Quantum ESPRESSO

Quantum ESPRESSO campaigns use
[`aiida-quantumespresso`](https://aiida-quantumespresso.readthedocs.io/) for
execution and `aiida-pseudo` for pseudopotential families.

Tasks:

- [SCF k-point convergence](kpoints/README.md)

Code-specific reusable builder logic remains in `src/goldilocks_data/`; this
directory documents and operates concrete data campaigns.
