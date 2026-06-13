import { useCallback, useMemo, useState } from 'react'
import { getCourseDetail, listCourseAttendees, listCourses } from '../api/courses'
import { QueryState } from '../components/QueryState'
import { useAsyncResource } from '../features/useAsyncResource'
import type { CourseAttendeeItem, CourseDetail, CourseListItem } from '../types/api'

interface CourseDetailPayload {
  detail: CourseDetail | null
  attendees: CourseAttendeeItem[]
}

const EMPTY_DETAIL: CourseDetailPayload = {
  detail: null,
  attendees: [],
}

const PAGE_SIZE = 25

function formatDate(value: string | null) {
  return value || '-'
}

function valueOrDash(value: string | number | null | undefined) {
  if (value === null || value === undefined) {
    return '-'
  }

  const text = String(value).trim()
  return text || '-'
}

function courseLabel(course: CourseListItem) {
  return course.curso_nombre || '-'
}

export function CoursesPage() {
  const [search, setSearch] = useState('')
  const [pageIndex, setPageIndex] = useState(0)
  const [selectedCandidateId, setSelectedCandidateId] = useState('')

  const offset = pageIndex * PAGE_SIZE
  const coursesQuery = useAsyncResource(
    () => listCourses(search, PAGE_SIZE, offset),
    { items: [], total: 0, limit: PAGE_SIZE, offset: 0 },
    [search, offset],
  )
  const courseRows = coursesQuery.data.items

  const selectedCourseId = useMemo(() => {
    if (!courseRows.length) {
      return ''
    }
    if (selectedCandidateId && courseRows.some((row) => row.curso_id === selectedCandidateId)) {
      return selectedCandidateId
    }
    return courseRows[0].curso_id
  }, [courseRows, selectedCandidateId])

  const loadSelectedCourse = useCallback(() => {
    if (!selectedCourseId) {
      return Promise.resolve(EMPTY_DETAIL)
    }
    return Promise.all([getCourseDetail(selectedCourseId), listCourseAttendees(selectedCourseId)]).then(
      ([detail, attendees]) => ({ detail, attendees: attendees.items }),
    )
  }, [selectedCourseId])

  const detailQuery = useAsyncResource(loadSelectedCourse, EMPTY_DETAIL, [loadSelectedCourse, selectedCourseId])
  const detailCourse = detailQuery.data.detail

  const hasPreviousPage = pageIndex > 0
  const hasNextPage = offset + courseRows.length < coursesQuery.data.total
  const currentPage = pageIndex + 1
  const totalPages = Math.max(1, Math.ceil(coursesQuery.data.total / PAGE_SIZE))

  return (
    <section className="courses-saas-page">
      <div className="courses-saas-workspace">
        <aside className="courses-list-panel">
          <div className="courses-list-head">
            <div className="courses-list-head-copy">
              <p className="courses-list-kicker">Cursos</p>
              <h2>Cursos</h2>
              <p>Listado read-only</p>
            </div>
            <span className="surface-chip">{courseRows.length} visibles</span>
          </div>

          <div className="courses-list-filters">
            <input
              className="input courses-search"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value)
                setPageIndex(0)
                setSelectedCandidateId('')
              }}
              placeholder="Buscar curso por nombre o codigo"
            />
          </div>

          <div className="courses-list-meta">
            <span className="surface-chip">
              Pagina {currentPage} de {totalPages}
            </span>
            <div className="courses-pager-actions" aria-label="Paginacion de cursos">
              <button
                type="button"
                className="courses-pager-btn"
                disabled={!hasPreviousPage}
                onClick={() => setPageIndex((prev) => Math.max(0, prev - 1))}
              >
                Anterior
              </button>
              <button
                type="button"
                className="courses-pager-btn"
                disabled={!hasNextPage}
                onClick={() => setPageIndex((prev) => prev + 1)}
              >
                Siguiente
              </button>
            </div>
          </div>

          <div className="courses-list-scroll">
            <QueryState
              loading={coursesQuery.loading}
              error={coursesQuery.error}
              empty={!courseRows.length}
              emptyMessage="No hay cursos para los filtros actuales."
            />

            {!!courseRows.length && (
              <div className="courses-list-grid">
                <div className="courses-list-header">
                  <div className="courses-list-cell">Nombre</div>
                  <div className="courses-list-cell">Fecha</div>
                </div>

                <div className="courses-list-body">
                  {courseRows.map((course) => {
                    const isSelected = course.curso_id === selectedCourseId

                    return (
                      <button
                        key={course.curso_id}
                        type="button"
                        className={`courses-list-row ${isSelected ? 'is-selected' : ''}`}
                        onClick={() => setSelectedCandidateId(course.curso_id)}
                      >
                        <span className="courses-list-cell courses-list-cell-name">{courseLabel(course)}</span>
                        <span className="courses-list-cell">{formatDate(course.curso_fecha)}</span>
                      </button>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        </aside>

        <section className="courses-detail-panel">
          <div className="courses-detail-card">
            <div className="courses-section-head">
              <div>
                <p className="courses-detail-kicker">Modulo read-only</p>
                <h3>Detalle de curso</h3>
                <p>Ficha compacta sin mutaciones.</p>
              </div>
              {!!detailCourse && <span className="surface-chip">Fecha {formatDate(detailCourse.curso_fecha)}</span>}
            </div>

            {!selectedCourseId && <div className="state">Selecciona un curso para ver el detalle.</div>}

            {!!selectedCourseId && (
              <QueryState
                loading={detailQuery.loading}
                error={detailQuery.error}
                empty={!detailCourse}
                emptyMessage="No se encontro detalle para el curso seleccionado."
              />
            )}

            {!!detailCourse && (
              <div className="courses-detail-grid">
                <div className="courses-field-row courses-field-row-top">
                  <label className="courses-field-name">
                    <span>Nombre</span>
                    <input className="input courses-field" readOnly value={valueOrDash(detailCourse.curso_nombre)} />
                  </label>
                  <label className="courses-field-date">
                    <span>Fecha</span>
                    <input className="input courses-field" readOnly value={formatDate(detailCourse.curso_fecha)} />
                  </label>
                </div>

                <div className="courses-field-row courses-field-row-bottom">
                  <label className="courses-field-code">
                    <span>Cod. interno</span>
                    <input className="input courses-field" readOnly value="-" />
                  </label>
                </div>

                <section className="courses-attendees-panel">
                  <div className="courses-section-head courses-section-head-sub">
                    <div>
                      <h3>Asistentes</h3>
                      <p>Listado read-only de asistentes del curso seleccionado.</p>
                    </div>
                    <span className="surface-chip">{detailQuery.data.attendees.length} asistentes</span>
                  </div>

                  {!detailQuery.data.attendees.length && <div className="state">Sin asistentes registrados.</div>}

                  {!!detailQuery.data.attendees.length && (
                    <div className="courses-attendees-scroll">
                      <div className="courses-attendees-list">
                        <div className="courses-attendees-header">
                          <div className="courses-attendees-cell">Nombre</div>
                          <div className="courses-attendees-cell">Empresa</div>
                          <div className="courses-attendees-cell">Confirmado</div>
                        </div>

                        <div className="courses-attendees-body">
                          {detailQuery.data.attendees.map((attendee) => (
                            <div key={attendee.id} className="courses-attendees-row">
                              <span className="courses-attendees-cell courses-attendees-cell-name">{valueOrDash(attendee.nombre)}</span>
                              <span className="courses-attendees-cell">{valueOrDash(attendee.empresa)}</span>
                              <span className="courses-attendees-cell">{attendee.confirmado ? 'Si' : 'No'}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </section>
              </div>
            )}
          </div>
        </section>
      </div>
    </section>
  )
}
