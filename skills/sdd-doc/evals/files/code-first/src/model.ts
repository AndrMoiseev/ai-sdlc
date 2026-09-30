export namespace Sales {
  export interface Customer { id: string; legalName: string }
  export function invoice(customer: Customer) { return { customerId: customer.id }; }
}
export namespace Transport {
  export interface Client { send(payload: string): Promise<void> }
}
export namespace Inventory {
  export interface Reservation { orderId: string; expiresAt: number }
  export function release(reservation: Reservation) { return { releasedOrder: reservation.orderId }; }
  export interface Allocation { orderId: string; expiresAt: number }
  export function legacyReserve(orderId: string): Allocation { return { orderId, expiresAt: Date.now()+60000 }; }
  export function reserve(orderId: string): Reservation { return legacyReserve(orderId); }
}
export namespace Fulfillment {
  export interface DispatchBatch { shipmentIds: string[] }
  export function dispatch(batch: DispatchBatch) { return batch.shipmentIds.map(id => ({ id, sent: true })); }
}
