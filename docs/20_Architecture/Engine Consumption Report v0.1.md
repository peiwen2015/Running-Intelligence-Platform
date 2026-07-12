# Engine Consumption Report v0.1

This report proves the first minimal Narrative Engine consumption slice for Recovery + Load Build.

| Scenario | Recovery Domain Input | Build Inputs | Engine Output | Rule | Domain Consumption |
|---|---|---|---|---|---|
| Scenario 1 | PLANNED_RECOVERY | load=+15%; recovery_completed=True; long_run_continuity=True; quality_distributed=True; rhythm_stable=True; multi_period=stable_rising | CONTROLLED_BUILD<br>Recovery has been absorbed and the new load is still arriving in a stable, repeatable structure. | KC-BLD-004 | recovery + build |
| Scenario 2 | REACTIVE_RECOVERY | load=+15%; recovery_completed=False; long_run_continuity=True; quality_distributed=True; rhythm_stable=True; multi_period=stable_rising | OVERLOAD<br>Stress rose before the prior fatigue signal was truly absorbed. | KC-BLD-003 | recovery + build |
| Scenario 3 | FORCED_RECOVERY | load=+20%; recovery_completed=False; long_run_continuity=False; quality_distributed=False; rhythm_stable=False; multi_period=stable_rising | OVERLOAD<br>Build cannot be treated as productive because recovery was externally interrupted before load rose again. | KC-BLD-002 | recovery + build |
| Scenario 4 | MAINTENANCE_WEEK | load=+9%; recovery_completed=True; long_run_continuity=True; quality_distributed=True; rhythm_stable=True; multi_period=rising_gradually | PROGRESSIVE_BUILD<br>Load is climbing steadily from block to block without forcing abrupt change. | KC-BLD-005 | recovery + build |
| Scenario 5 | PLANNED_RECOVERY | load=+22%; recovery_completed=False; long_run_continuity=False; quality_distributed=False; rhythm_stable=False; multi_period=stable_rising | AGGRESSIVE_BUILD<br>Stress is still rising, but the recovery or structure margin is getting thin. | KC-BLD-006 | recovery + build |
| Scenario 6 | MAINTENANCE_WEEK | load=+18%; recovery_completed=True; long_run_continuity=True; quality_distributed=True; rhythm_stable=True; multi_period=fragile_rising | UNSUSTAINABLE_BUILD<br>Load is still rising, but the direction is no longer repeatable across periods. | KC-BLD-001 | build only |

## Notes

- This is a minimal executable proof, not a full production rule set.
- The goal is to show that build interpretation changes when recovery knowledge changes.
- New knowledge domains should only be added after current domains fail to explain observed scenarios.