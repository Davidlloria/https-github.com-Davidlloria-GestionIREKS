import { apiDelete, apiGet, apiPatch, apiPost } from './http'
import type {
  OrderDocumentImportResponse,
  OrderItemRead,
  OrderJsonImportResponse,
  OrderListItem,
  OrderPendingRead,
  OrderRead,
} from '../types/api'

interface ListOrdersFilters {
  year?: string
  monthFrom?: number
  monthTo?: number
  almacenId?: string
}

export function listOrders(filters: ListOrdersFilters) {
  return apiGet<OrderListItem[]>('/orders', {
    year: filters.year,
    month_from: filters.monthFrom,
    month_to: filters.monthTo,
    almacen_id: filters.almacenId,
  })
}

export function getOrderDetail(orderId: string) {
  return apiGet<OrderRead>(`/orders/${orderId}`)
}

export function listOrderItems(orderId: string) {
  return apiGet<OrderItemRead[]>(`/orders/${orderId}/items`)
}

export function listOrderPending(orderId: string) {
  return apiGet<OrderPendingRead[]>(`/orders/${orderId}/pending`)
}

export function deleteOrder(orderId: string) {
  return apiDelete(`/orders/${orderId}`)
}

export function createOrder(payload: {
  almacen_id: string
  pedido_fecha: string
  pedido_numero: string
  lines: Array<{ articulo_id: string; uds: number }>
  is_pending: boolean
}) {
  return apiPost<OrderRead>('/orders', payload)
}

export function updateOrder(
  orderId: string,
  payload: {
    pedido_fecha: string
    pedido_numero: string
    lines: Array<{ articulo_id: string; uds: number }>
    submit_mode: string
  },
) {
  return apiPatch<OrderRead>(`/orders/${orderId}`, payload)
}

export function createOrderItem(orderId: string, payload: { articulo_id: string; articulo_cantidad: number }) {
  return apiPost<OrderItemRead>(`/orders/${orderId}/items`, payload)
}

export function updateOrderItem(itemId: string, payload: { articulo_id: string; articulo_cantidad: number }) {
  return apiPatch<OrderItemRead>(`/orders/items/${itemId}`, payload)
}

export function deleteOrderItem(itemId: string) {
  return apiDelete(`/orders/items/${itemId}`)
}

export function importOrderJson(payload: { almacen_id: string; source_path: string }) {
  return apiPost<OrderJsonImportResponse>('/orders/import/json', payload)
}

export function importOrderAlbaranPdf(orderId: string, payload: { source_path: string }) {
  return apiPost<OrderDocumentImportResponse>(`/orders/${orderId}/import/albaran-pdf`, payload)
}

export function importOrderFacturaPdf(orderId: string, payload: { source_path: string }) {
  return apiPost<OrderDocumentImportResponse>(`/orders/${orderId}/import/factura-pdf`, payload)
}
