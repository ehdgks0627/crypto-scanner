export class ScanSelectionModel {
  static targetIdsFromSearch(search: URLSearchParams): number[] {
    const singleId = this.validPositiveInteger(search.get("target_id"));
    if (singleId) {
      return [singleId];
    }

    const csvIds = search
      .get("target_ids")
      ?.split(",")
      .map((value) => this.validPositiveInteger(value))
      .filter((value): value is number => Boolean(value));

    return Array.from(new Set(csvIds ?? []));
  }

  private static validPositiveInteger(value: string | null | undefined): number | null {
    if (!value) {
      return null;
    }

    const parsed = Number(value);
    if (!Number.isInteger(parsed) || parsed <= 0) {
      return null;
    }

    return parsed;
  }
}
