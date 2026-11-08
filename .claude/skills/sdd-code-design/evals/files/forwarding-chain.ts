// This fixture is a complete, read-only source snapshot. File boundaries are comments.

// file: catalog.ts
export type Product = Readonly<{ sku: string; label: string; priceCents: number }>;
export interface ProductCatalog { find(sku: string): Promise<Product | undefined>; }
export class CatalogUnavailable extends Error {}

// file: sql-catalog.ts
export interface Rows { bySku(sku: string): Promise<{ sku: string; label: string; cents: number } | undefined>; }
export class SqlFailure extends Error {}
export class SqlProductCatalog implements ProductCatalog {
  constructor(private readonly rows: Rows) {}
  async find(sku: string): Promise<Product | undefined> {
    try {
      const row = await this.rows.bySku(sku);
      return row && { sku: row.sku, label: row.label, priceCents: row.cents };
    } catch (error) {
      if (error instanceof SqlFailure) throw new CatalogUnavailable();
      throw error;
    }
  }
}

// file: product-reader.ts
export class ProductReader implements ProductCatalog {
  constructor(private readonly catalog: ProductCatalog) {}
  find(sku: string): Promise<Product | undefined> { return this.catalog.find(sku); }
}

// file: product-gateway.ts
export class ProductGateway implements ProductCatalog {
  constructor(private readonly reader: ProductCatalog) {}
  find(sku: string): Promise<Product | undefined> { return this.reader.find(sku); }
}

// file: callers.ts
export async function priceTag(catalog: ProductCatalog, sku: string) {
  const product = await catalog.find(sku);
  return product ? product.priceCents : undefined;
}
export async function inventoryLabel(catalog: ProductCatalog, sku: string) {
  const product = await catalog.find(sku);
  return product?.label;
}

// file: composition.ts
export function makeCatalog(rows: Rows): ProductCatalog {
  return new ProductGateway(new ProductReader(new SqlProductCatalog(rows)));
}

// file: contracts.test.ts (recorded assertions; test harness omitted)
export const existingChecks = [
  "priceTag and inventoryLabel each accept an in-memory ProductCatalog",
  "SqlProductCatalog maps cents to priceCents and SqlFailure to CatalogUnavailable",
  "ProductReader and ProductGateway forwarding tests assert one call with the original sku"
];
// There are no other consumers, factories, interceptors, lifecycle hooks, or registrations in this snapshot.
