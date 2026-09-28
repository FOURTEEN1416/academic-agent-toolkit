# Architecture

## Conclusion

This project is moving toward a small work kernel.

The kernel is the part that should understand the goal, organize useful skills into bounded work units, prepare executable work, verify what the evidence can prove, and leave proof behind.

The shortest correct explanation is:

`task card -> build work model -> bind skills -> produce evidence or needs_execution -> verify scope -> prove only what is proven`

If a change makes the system harder to explain than that, the design is drifting.

## What The System Is

Vibe-Skills should not be understood as a giant skill menu with a smarter router on top.

It should be understood as:

- a small kernel that owns the work loop
- a skill surface that supplies capability
- a compatibility layer that protects older entrypoints while they lose semantic authority
- thin host adapters for install, checks, and environment-specific execution

Work matters more than routing.
Skills are materials, not the product.

For this submit boundary, responsibilities stay narrow:

- the installer owns file placement and receipt-owned update safety
- the router owns which skills are bound to bounded work
- the runtime owns stage state, scaffold status, and execution evidence
- verification owns what the available evidence can and cannot prove

`bound` is not `used`, and scaffold output is not completed work.

## Main Layers

### 1. Work Kernel

This is the semantic core.

It owns:

- task understanding
- skill finding
- plan construction
- execution
- verification
- proof and run state

Primary shape:

- `packages/runtime-core/src/vgo_runtime/kernel/`

The kernel should stay short and legible. It is the main place to change how the system understands, organizes, completes, and proves work.

### 2. Skill Surface

This is where capability enters the system.

The steady-state direction is:

- local skills are the normal extension path
- starter skills stay small
- indexes are cache, not truth

Skills should describe themselves close to where they live. Adding one normal skill should not require router surgery.

### 3. Compatibility Projection

This layer exists so older runtime surfaces can still receive results in the shape they expect.

It may:

- project kernel results into older packets or summaries
- preserve public entry stability during migration
- keep historical contracts readable while they are still needed

It must not:

- redefine task meaning
- own the plan
- quietly become the real control plane again

### 4. Host Adapters

These are the environment-facing edges.

They include:

- install scripts
- check scripts
- host wiring
- leaf execution bridges when a host truly needs them

PowerShell still has value here on Windows, but it is no longer the place where the system should decide what the work means.

## Control Flow

The intended hot path is small:

1. capture the goal as a task card
2. build a bounded work model
3. bind skills where they help that work model
4. execute those units
5. verify against completion criteria
6. record proof and summary

Anything outside this path should justify its existence as either:

- compatibility support
- host support
- evidence support

If it cannot do that, it is probably residue.

## Boundary Rule

The kernel owns meaning.

The compatibility layer may translate, but it must not decide.

The host layer may run, but it must not interpret.

The skill layer may contribute capability, but it must not seize the workflow.

This is the core boundary discipline that keeps the kernel small and the system evolvable.

## What Is Still Transitional

The current repository still contains older routing, governance, and canonical-entry surfaces.

Those surfaces are now treated as migration-era shells unless they are explicitly listed as authority in the kernel boundary demotion map:

- `config/kernel-boundary-demotion-matrix.json`

That means a file can still be live without still being the place where new meaning should be added.
If one semantic fact still appears in several current runtime surfaces, the residue ledger inside that same boundary file should say which copy is preferred and when the others are supposed to retire.

## How To Judge Progress

A good change does not merely make the router cleaner.

A good change should make at least one of these things more true:

- the system finishes more real work
- proof becomes tighter
- adding or changing a skill gets cheaper
- task understanding gets easier to change in one place
- the next maintainer can find the right entrypoint faster

The benchmark and boundary framework lives here:

- `docs/architecture/kernel-evaluation-framework.md`

Use that framework to judge whether a change improved the work kernel or only rearranged the old control plane.

That judgment should include more than code shape alone.
The public story, benchmark comparison discipline, and maintainer validation gates should all keep pointing at the same work-first system.
Read that progress through three separate ledgers: work capability, author experience, and migration debt.
