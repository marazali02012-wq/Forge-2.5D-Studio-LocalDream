# R68 experimental checkpoint

Base R67 064c8340cbc1c379fad4823922ae580a4676e119. No new AI inference.
Local synthetic tube benchmark only; not R67 character assets, not actual animation clips.
Six width candidates tested across +/-45 and +/-90 degrees on two bend axes.
Elbow mean of per-pose p95 absolute edge strain 25.9834% -> 8.7682%; mean compression 1.0773% -> 0.5315%; mean face area loss 2.2774% -> 1.1628%. Signed capped-tube volume ratio at one 90-degree pose 0.986607 -> 0.989173, not proof of no self-intersection or anatomical volume retention.
Knee, shoulder, hip synthetic tubes: no accepted candidate; old weights preserved.
Two unittest cases passed locally, including duplicate seam weight equality and distant vertex preservation. Visual inspection on synthetic meshes only. Full 26-joint R67 GLB, real independent character families, walk/attack/hit/death, Android, full UI and export regression unverified.
The experimental module is not enabled by default and is not yet integrated into build_rig. Next: real GLB clip-level comparison including exact R67 sole drift, rigid component and source UV preservation. P0 single-image AI inference remains open.
