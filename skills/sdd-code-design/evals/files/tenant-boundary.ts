// This fixture is a complete, read-only source snapshot. File boundaries are comments.

// file: vendor-client.ts
export type VendorRow = { id: string; tenant_key: string; title: string };
export interface VendorClient {
  // The vendor SDK can query any tenant; credentials are application-wide.
  find(input: { tenant_key: string; row_id: string }): Promise<VendorRow | undefined>;
}
export class VendorUnavailable extends Error {}

// file: tenant-reports.ts
export type Report = { id: string; title: string };
export class ReportsUnavailable extends Error {}
export interface Reports { get(id: string): Promise<Report | undefined>; }
export class TenantReports implements Reports {
  constructor(private readonly client: VendorClient, private readonly tenant: string) {}
  async get(id: string): Promise<Report | undefined> {
    try {
      const row = await this.client.find({ tenant_key: this.tenant, row_id: id });
      return row && { id: row.id, title: row.title };
    } catch (error) {
      if (error instanceof VendorUnavailable) throw new ReportsUnavailable();
      throw error;
    }
  }
}

// file: composition.ts
export function reportsFor(request: { verifiedTenant: string }, client: VendorClient): Reports {
  // verifiedTenant comes from the authenticated server session; not from request parameters.
  return new TenantReports(client, request.verifiedTenant);
}

// file: report-page.ts
export async function reportPage(reports: Reports, path: { reportId: string }) {
  const report = await reports.get(path.reportId);
  return report ? report.title : "Not found";
}

// file: csv-export.ts
export async function exportTitle(reports: Reports, reportId: string) {
  const report = await reports.get(reportId);
  return report ? '"' + report.title.replaceAll('"', '""') + '"' : "";
}

// file: tenant-reports.test.ts (recorded assertions; test harness omitted)
export const existingChecks = [
  "request verifiedTenant=team-a and path reportId=r7 calls find({tenant_key:team-a,row_id:r7})",
  "returned Report has id/title only; tenant_key is not exposed",
  "VendorUnavailable is translated to ReportsUnavailable",
  "report-page test injects Reports without importing the vendor SDK"
];
