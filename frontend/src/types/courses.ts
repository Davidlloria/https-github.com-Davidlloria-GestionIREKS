export interface CourseListItem {
  curso_id: string
  curso_nombre: string
  curso_fecha: string | null
}

export type CourseDetail = CourseListItem

export interface CourseAttendeeItem {
  id: string
  nombre: string
  empresa: string
  confirmado: boolean
  observaciones: string
}

export interface CourseListResponse {
  total: number
  limit: number
  offset: number
  items: CourseListItem[]
}

export interface CourseAttendeeListResponse {
  total: number
  limit: number
  offset: number
  items: CourseAttendeeItem[]
}
