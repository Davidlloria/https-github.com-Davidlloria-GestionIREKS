import { useCallback, useMemo, useState } from 'react'
import { getCourseDetail, listCourseAttendees, listCourses } from '../api/courses'
import { QueryState } from '../components/QueryState'
import { StatCard } from '../components/StatCard'
import { useAsyncResource } from '../features/useAsyncResource'
import type { CourseAttendeeItem, CourseDetail } from '../types/api'

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

  const totals = useMemo(() => {
    const withDate = courseRows.filter((row) => !!row.curso_fecha).length
    const withAttendees = detailQuery.data.attendees.length
    return {
      total: coursesQuery.data.total,
      withDate,
      withAttendees,
    }
  }, [courseRows, coursesQuery.data.total, detailQuery.data.attendees.length])

  const hasPreviousPage = pageIndex > 0
  const hasNextPage = offset + courseRows.length < coursesQuery.data.total
  const currentPage = pageIndex + 1
  const totalPages = Math.max(1, Math.ceil(coursesQuery.data.total / PAGE_SIZE))

  return (
    <section className="page-grid">
      <div className="toolbar">
        <input
          className="input"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value)
            setPageIndex(0)
          }}
          placeholder="Buscar curso por nombre o codigo"
        />
        <button type="button" className="action-btn" disabled={!hasPreviousPage} onClick={() => setPageIndex((prev) => Math.max(0, prev - 1))}>
          Anterior
        </button>
        <button type="button" className="action-btn" disabled={!hasNextPage} onClick={() => setPageIndex((prev) => prev + 1)}>
          Siguiente
        </button>
        <span className="state">
          Pagina {currentPage} de {totalPages}
        </span>
      </div>

      <div className="cards">
        <StatCard label="Total cursos" value={totals.total} />
        <StatCard label="Con fecha" value={totals.withDate} />
        <StatCard label="Asistentes seleccionados" value={totals.withAttendees} />
        <StatCard label="Vista" value="Cursos" />
      </div>

      <QueryState
        loading={coursesQuery.loading}
        error={coursesQuery.error}
        empty={!courseRows.length}
        emptyMessage="No hay cursos para los filtros actuales."
      />

      {!!courseRows.length && (
        <div className="split-panel">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Curso ID</th>
                  <th>Nombre</th>
                  <th>Fecha</th>
                </tr>
              </thead>
              <tbody>
                {courseRows.map((course) => (
                  <tr
                    key={course.curso_id}
                    className={course.curso_id === selectedCourseId ? 'row-selected' : ''}
                    onClick={() => setSelectedCandidateId(course.curso_id)}
                  >
                    <td>{course.curso_id}</td>
                    <td>{course.curso_nombre || '-'}</td>
                    <td>{formatDate(course.curso_fecha)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <aside className="detail-panel">
            {!selectedCourseId && <div className="state">Selecciona un curso para ver el detalle.</div>}
            {!!selectedCourseId && (
              <>
                <QueryState
                  loading={detailQuery.loading}
                  error={detailQuery.error}
                  empty={!detailQuery.data.detail}
                  emptyMessage="No se encontro detalle para el curso seleccionado."
                />

                {!!detailQuery.data.detail && (
                  <>
                    <dl className="detail-list">
                      <div>
                        <dt>Curso ID</dt>
                        <dd>{detailQuery.data.detail.curso_id}</dd>
                      </div>
                      <div>
                        <dt>Nombre</dt>
                        <dd>{detailQuery.data.detail.curso_nombre || '-'}</dd>
                      </div>
                      <div>
                        <dt>Fecha</dt>
                        <dd>{formatDate(detailQuery.data.detail.curso_fecha)}</dd>
                      </div>
                    </dl>

                    <div className="related-block">
                      <h3>Asistentes</h3>
                      {!detailQuery.data.attendees.length && <div className="state">Sin asistentes.</div>}
                      {!!detailQuery.data.attendees.length && (
                        <div className="table-wrap">
                          <table>
                            <thead>
                              <tr>
                                <th>Nombre</th>
                                <th>Empresa</th>
                                <th>Confirmado</th>
                              </tr>
                            </thead>
                            <tbody>
                              {detailQuery.data.attendees.map((attendee) => (
                                <tr key={attendee.id}>
                                  <td>{attendee.nombre || '-'}</td>
                                  <td>{attendee.empresa || '-'}</td>
                                  <td>{attendee.confirmado ? 'Si' : 'No'}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  </>
                )}
              </>
            )}
          </aside>
        </div>
      )}
    </section>
  )
}
