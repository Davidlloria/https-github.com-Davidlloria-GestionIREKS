import { apiDelete, apiGet } from './http'
import type { OrderItemRead, OrderListItem, OrderPendingRead, OrderRead } from '../types/api'

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
