import { apiGet } from './http'
import type { CourseAttendeeListResponse, CourseDetail, CourseListResponse } from '../types/api'

export function listCourses(search: string, limit?: number, offset?: number) {
  return apiGet<CourseListResponse>('/courses', { q: search, limit, offset })
}

export function getCourseDetail(courseId: string) {
  return apiGet<CourseDetail>(`/courses/${courseId}`)
}

export function listCourseAttendees(courseId: string) {
  return apiGet<CourseAttendeeListResponse>(`/courses/${courseId}/attendees`)
}
