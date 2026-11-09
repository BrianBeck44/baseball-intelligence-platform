import type { PlayerSeasonCaOps } from "../types/playerSeasonCaOps";

export const MINIMUM_PLATE_APPEARANCES = 200;

export interface ComparableCaOpsRow extends PlayerSeasonCaOps {
  observed_ops: number;
  ca_ops: number;
}

export function hasQualifyingPlateAppearances(
  row: PlayerSeasonCaOps,
): boolean {
  return (
    row.plate_appearances !== null &&
    row.plate_appearances >= MINIMUM_PLATE_APPEARANCES
  );
}

export function hasComparableOps(
  row: PlayerSeasonCaOps,
): row is ComparableCaOpsRow {
  return (
    hasQualifyingPlateAppearances(row) &&
    row.observed_ops !== null &&
    row.ca_ops !== null
  );
}

export function topPlayersByCaOps(
  rows: PlayerSeasonCaOps[],
  limit = 10,
): PlayerSeasonCaOps[] {
  return rows
    .filter(
      (row) => row.ca_ops !== null && hasQualifyingPlateAppearances(row),
    )
    .sort((left, right) => (right.ca_ops as number) - (left.ca_ops as number))
    .slice(0, limit);
}

export function bottomPlayersByCaOps(
  rows: PlayerSeasonCaOps[],
  limit = 10,
): PlayerSeasonCaOps[] {
  return rows
    .filter(
      (row) => row.ca_ops !== null && hasQualifyingPlateAppearances(row),
    )
    .sort((left, right) => (left.ca_ops as number) - (right.ca_ops as number))
    .slice(0, limit);
}

export function topPositiveCaOpsAdjustments(
  rows: PlayerSeasonCaOps[],
  limit = 10,
): ComparableCaOpsRow[] {
  return rows
    .filter(hasComparableOps)
    .filter((row) => row.ca_ops > row.observed_ops)
    .sort(
      (left, right) =>
        right.ca_ops - right.observed_ops - (left.ca_ops - left.observed_ops),
    )
    .slice(0, limit);
}

export function topNegativeCaOpsAdjustments(
  rows: PlayerSeasonCaOps[],
  limit = 10,
): ComparableCaOpsRow[] {
  return rows
    .filter(hasComparableOps)
    .filter((row) => row.observed_ops > row.ca_ops)
    .sort(
      (left, right) =>
        right.observed_ops -
        right.ca_ops -
        (left.observed_ops - left.ca_ops),
    )
    .slice(0, limit);
}
