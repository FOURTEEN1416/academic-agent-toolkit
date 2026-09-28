# Skill Catalog

This package owns detached catalog metadata for official VCO skills.

It is not a runtime owner.
It exists so installer and distribution layers can consume catalog descriptors without traversing bundled runtime topology.

The exported catalog is profile-aware.
`minimal` and `full` do not maintain a second copy of skill-selection truth here.
Each catalog profile points back to the matching runtime-core packaging projection, so changing the starter set only requires changing one source of truth.
