import { apiDelete, apiGet, apiPatch, apiPost, apiPostForm } from './http'
import type {
  OrderDocumentImportResponse,
  OrderItemRead,
  OrderJsonImportResponse,
  OrderListItem,
  OrderPendingRead,
  PaginatedList,
  OrderRead,
} from '../types/api'

interface ListOrdersFilters {
  year?: string
  monthFrom?: number
  monthTo?: number
  almacenId?: string
  limit?: number
  offset?: number
}

export function listOrders(filters: ListOrdersFilters) {
  return apiGet<PaginatedList<OrderListItem>>('/orders', {
    year: filters.year,
    month_from: filters.monthFrom,
    month_to: filters.monthTo,
    almacen_id: filters.almacenId,
    limit: filters.limit,
    offset: filters.offset,
  })
}

export function getOrderDetail(orderId: string) {
  return apiGet<OrderRead>(`/orders/${orderId}`)
}

export function listOrderItems(orderId: string, limit?: number, offset?: number) {
  return apiGet<PaginatedList<OrderItemRead>>(`/orders/${orderId}/items`, { limit, offset })
}

export function listOrderPending(orderId: string, limit?: number, offset?: number) {
  return apiGet<PaginatedList<OrderPendingRead>>(`/orders/${orderId}/pending`, { limit, offset })
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

export function importOrderJsonUpload(payload: { almacen_id: string; file: File }) {
  const form = new FormData()
  form.append('almacen_id', payload.almacen_id)
  form.append('file', payload.file)
  return apiPostForm<OrderJsonImportResponse>('/orders/import/json/upload', form)
}

export function importOrderAlbaranPdf(orderId: string, payload: { source_path: string }) {
  return apiPost<OrderDocumentImportResponse>(`/orders/${orderId}/import/albaran-pdf`, payload)
}

export function importOrderAlbaranPdfUpload(orderId: string, payload: { file: File }) {
  const form = new FormData()
  form.append('file', payload.file)
  return apiPostForm<OrderDocumentImportResponse>(`/orders/${orderId}/import/albaran-pdf/upload`, form)
}

export function importOrderFacturaPdf(orderId: string, payload: { source_path: string }) {
  return apiPost<OrderDocumentImportResponse>(`/orders/${orderId}/import/factura-pdf`, payload)
}

export function importOrderFacturaPdfUpload(orderId: string, payload: { file: File }) {
  const form = new FormData()
  form.append('file', payload.file)
  return apiPostForm<OrderDocumentImportResponse>(`/orders/${orderId}/import/factura-pdf/upload`, form)
}
