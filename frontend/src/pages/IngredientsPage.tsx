import { useCallback, useMemo, useState } from 'react'
import {
  createIreksTarifa,
  deleteIreksTarifa,
  deleteIreksIngredient,
  deleteStdIngredient,
  getIreksIngredientDetail,
  getIreksNutrition,
  getStdIngredientDetail,
  getStdNutrition,
  listIreksIngredients,
  listIreksTarifas,
  listStdIngredients,
  listStdPrices,
  updateIreksIngredient,
  updateIreksTarifa,
  updateStdActive,
  updateStdIngredient,
} from '../api/ingredients'
import { QueryState } from '../components/QueryState'
import { StatCard } from '../components/StatCard'
import { useAsyncResource } from '../features/useAsyncResource'
import type {
  IngredientIreksRead,
  IngredientStdRead,
  MateriaPrimaPrecioRead,
  NutritionValues,
  TarifaPrecioIreksRead,
} from '../types/api'

type IngredientMode = 'ireks' | 'std'

interface IreksDetailPayload {
  detail: IngredientIreksRead | null
  nutrition: NutritionValues | null
  tarifas: TarifaPrecioIreksRead[]
}

interface StdDetailPayload {
  detail: IngredientStdRead | null
  nutrition: NutritionValues | null
  prices: MateriaPrimaPrecioRead[]
}

interface StdEditForm {
  articulo_descripcion: string
  pvp_formato: string
  pvp_unidad_medida: string
}

interface IreksEditForm {
  articulo_referencia: string
  articulo_referencia_corta: string
  articulo_descripcion: string
  categoria: string
}

interface IreksTarifaForm {
  tarifa_ano: string
  precio_fabricante: string
  precio_distribuidor: string
  descuento_pct: string
}

const EMPTY_IREKS_DETAIL: IreksDetailPayload = {
  detail: null,
  nutrition: null,
  tarifas: [],
}

const EMPTY_STD_DETAIL: StdDetailPayload = {
  detail: null,
  nutrition: null,
  prices: [],
}

const EMPTY_STD_EDIT_FORM: StdEditForm = {
  articulo_descripcion: '',
  pvp_formato: '',
  pvp_unidad_medida: '',
}

const EMPTY_IREKS_EDIT_FORM: IreksEditForm = {
  articulo_referencia: '',
  articulo_referencia_corta: '',
  articulo_descripcion: '',
  categoria: '',
}

const EMPTY_IREKS_TARIFA_FORM: IreksTarifaForm = {
  tarifa_ano: '',
  precio_fabricante: '',
  precio_distribuidor: '',
  descuento_pct: '',
}

export function IngredientsPage() {
  const [mode, setMode] = useState<IngredientMode>('ireks')
  const [search, setSearch] = useState('')
  const [activityFilter, setActivityFilter] = useState('all')
  const [selectedIreksCandidateId, setSelectedIreksCandidateId] = useState('')
  const [selectedStdCandidateId, setSelectedStdCandidateId] = useState('')
  const [stdActiveLoading, setStdActiveLoading] = useState(false)
  const [stdActiveMessage, setStdActiveMessage] = useState('')
  const [stdActiveError, setStdActiveError] = useState('')
  const [ireksActiveLoading, setIreksActiveLoading] = useState(false)
  const [ireksActiveMessage, setIreksActiveMessage] = useState('')
  const [ireksActiveError, setIreksActiveError] = useState('')
  const [ireksDeleteLoading, setIreksDeleteLoading] = useState(false)
  const [ireksDeleteMessage, setIreksDeleteMessage] = useState('')
  const [ireksDeleteError, setIreksDeleteError] = useState('')
  const [ireksListLoading, setIreksListLoading] = useState(false)
  const [ireksListMessage, setIreksListMessage] = useState('')
  const [ireksListError, setIreksListError] = useState('')
  const [stdEditForm, setStdEditForm] = useState<StdEditForm>(EMPTY_STD_EDIT_FORM)
  const [stdEditTargetId, setStdEditTargetId] = useState('')
  const [stdEditLoading, setStdEditLoading] = useState(false)
  const [stdEditMessage, setStdEditMessage] = useState('')
  const [stdEditError, setStdEditError] = useState('')
  const [stdDeleteLoading, setStdDeleteLoading] = useState(false)
  const [stdDeleteMessage, setStdDeleteMessage] = useState('')
  const [stdDeleteError, setStdDeleteError] = useState('')
  const [ireksEditForm, setIreksEditForm] = useState<IreksEditForm>(EMPTY_IREKS_EDIT_FORM)
  const [ireksEditTargetId, setIreksEditTargetId] = useState('')
  const [ireksEditLoading, setIreksEditLoading] = useState(false)
  const [ireksEditMessage, setIreksEditMessage] = useState('')
  const [ireksEditError, setIreksEditError] = useState('')
  const [selectedIreksTarifaId, setSelectedIreksTarifaId] = useState<number | null>(null)
  const [ireksTarifaForm, setIreksTarifaForm] = useState<IreksTarifaForm>(EMPTY_IREKS_TARIFA_FORM)
  const [ireksTarifaLoading, setIreksTarifaLoading] = useState(false)
  const [ireksTarifaMessage, setIreksTarifaMessage] = useState('')
  const [ireksTarifaError, setIreksTarifaError] = useState('')

  const ireksQuery = useAsyncResource(
    () => listIreksIngredients(search, activityFilter),
    { rows: [], catalogs: { distribuidores: [], fabricantes: [], familias: [], subfamilias: [], envases: [] } },
    [search, activityFilter],
  )
  const stdQuery = useAsyncResource(
    () => listStdIngredients(search, activityFilter),
    [],
    [search, activityFilter],
  )

  const selectedIreks = useMemo(() => {
    if (!ireksQuery.data.rows.length) {
      return null as IngredientIreksRead | null
    }
    const explicit = ireksQuery.data.rows.find((row) => row.articulo_id === selectedIreksCandidateId)
    return explicit ?? ireksQuery.data.rows[0]
  }, [ireksQuery.data.rows, selectedIreksCandidateId])

  const selectedStd = useMemo(() => {
    if (!stdQuery.data.length) {
      return null as IngredientStdRead | null
    }
    const explicit = stdQuery.data.find((row) => row.articulo_id === selectedStdCandidateId)
    return explicit ?? stdQuery.data[0]
  }, [stdQuery.data, selectedStdCandidateId])

  const loadIreksDetail = useCallback(() => {
    if (!selectedIreks || selectedIreks.id === null) {
      return Promise.resolve(EMPTY_IREKS_DETAIL)
    }
    const articuloId = selectedIreks.articulo_id
    return Promise.all([
      getIreksIngredientDetail(selectedIreks.id),
      getIreksNutrition(articuloId),
      listIreksTarifas(articuloId),
    ]).then(([detail, nutrition, tarifas]) => ({ detail, nutrition, tarifas }))
  }, [selectedIreks])

  const ireksDetailQuery = useAsyncResource(loadIreksDetail, EMPTY_IREKS_DETAIL, [loadIreksDetail, selectedIreks?.id])

  const loadStdDetail = useCallback(() => {
    if (!selectedStd) {
      return Promise.resolve(EMPTY_STD_DETAIL)
    }
    const articuloId = selectedStd.articulo_id
    return Promise.all([
      getStdIngredientDetail(articuloId),
      getStdNutrition(articuloId),
      listStdPrices(articuloId),
    ]).then(([detail, nutrition, prices]) => ({ detail, nutrition, prices }))
  }, [selectedStd])

  const stdDetailQuery = useAsyncResource(loadStdDetail, EMPTY_STD_DETAIL, [loadStdDetail, selectedStd?.articulo_id])

  const totals = useMemo(() => {
    const ireksActive = ireksQuery.data.rows.filter((row) => row.articulo_status_activo).length
    const ireksInList = ireksQuery.data.rows.filter((row) => row.articulo_status_en_lista).length
    const stdActive = stdQuery.data.filter((row) => row.activo).length
    return {
      ireksTotal: ireksQuery.data.rows.length,
      ireksActive,
      ireksInList,
      stdTotal: stdQuery.data.length,
      stdActive,
    }
  }, [ireksQuery.data, stdQuery.data])

  const currentStdEditForm = useMemo(() => {
    const detail = stdDetailQuery.data.detail
    if (!detail) {
      return EMPTY_STD_EDIT_FORM
    }
    if (stdEditTargetId !== detail.articulo_id) {
      return {
        articulo_descripcion: detail.articulo_descripcion || '',
        pvp_formato: String(detail.pvp_formato ?? 0),
        pvp_unidad_medida: String(detail.pvp_unidad_medida ?? 0),
      }
    }
    return stdEditForm
  }, [stdDetailQuery.data.detail, stdEditForm, stdEditTargetId])

  const currentIreksEditForm = useMemo(() => {
    const detail = ireksDetailQuery.data.detail
    if (!detail) {
      return EMPTY_IREKS_EDIT_FORM
    }
    if (ireksEditTargetId !== detail.articulo_id) {
      return {
        articulo_referencia: detail.articulo_referencia || '',
        articulo_referencia_corta: detail.articulo_referencia_corta || '',
        articulo_descripcion: detail.articulo_descripcion || '',
        categoria: detail.categoria || '',
      }
    }
    return ireksEditForm
  }, [ireksDetailQuery.data.detail, ireksEditForm, ireksEditTargetId])

  const selectedIreksTarifa = useMemo(
    () =>
      ireksDetailQuery.data.tarifas.find(
        (tarifa) => tarifa.id !== null && tarifa.id === selectedIreksTarifaId,
      ) ?? null,
    [ireksDetailQuery.data.tarifas, selectedIreksTarifaId],
  )

  const formatWeight = (value: unknown) => {
    const numeric = Number(value)
    return Number.isFinite(numeric) ? numeric.toFixed(2) : '0.00'
  }

  const toggleStdActive = async () => {
    if (!stdDetailQuery.data.detail || stdActiveLoading) {
      return
    }
    setStdActiveLoading(true)
    setStdActiveError('')
    setStdActiveMessage('')
    const current = stdDetailQuery.data.detail
    const nextActive = !current.activo
    try {
      await updateStdActive(current.articulo_id, nextActive)
      await Promise.all([stdQuery.reload(), stdDetailQuery.reload()])
      setStdActiveMessage(nextActive ? 'Materia prima activada.' : 'Materia prima desactivada.')
    } catch (error: unknown) {
      setStdActiveError(error instanceof Error ? error.message : 'No se pudo actualizar el estado de la materia prima.')
    } finally {
      setStdActiveLoading(false)
    }
  }

  const saveStdEdition = async () => {
    const detail = stdDetailQuery.data.detail
    if (!detail || stdEditLoading) {
      return
    }
    const pvpFormato = Number.parseFloat(currentStdEditForm.pvp_formato.replace(',', '.'))
    const pvpUnidad = Number.parseFloat(currentStdEditForm.pvp_unidad_medida.replace(',', '.'))
    if (!currentStdEditForm.articulo_descripcion.trim()) {
      setStdEditError('La descripcion es obligatoria.')
      setStdEditMessage('')
      return
    }
    if (!Number.isFinite(pvpFormato) || pvpFormato < 0) {
      setStdEditError('PVP formato debe ser un numero mayor o igual que 0.')
      setStdEditMessage('')
      return
    }
    if (!Number.isFinite(pvpUnidad) || pvpUnidad < 0) {
      setStdEditError('PVP unidad de medida debe ser un numero mayor o igual que 0.')
      setStdEditMessage('')
      return
    }

    setStdEditLoading(true)
    setStdEditError('')
    setStdEditMessage('')
    try {
      const updated = await updateStdIngredient(detail.articulo_id, {
        articulo_descripcion: currentStdEditForm.articulo_descripcion.trim(),
        pvp_formato: pvpFormato,
        pvp_unidad_medida: pvpUnidad,
      })
      await Promise.all([stdQuery.reload(), stdDetailQuery.reload()])
      setStdEditTargetId(updated.articulo_id)
      setStdEditForm({
        articulo_descripcion: updated.articulo_descripcion || '',
        pvp_formato: String(updated.pvp_formato ?? 0),
        pvp_unidad_medida: String(updated.pvp_unidad_medida ?? 0),
      })
      setStdEditMessage('Materia prima STD actualizada.')
    } catch (error: unknown) {
      setStdEditError(error instanceof Error ? error.message : 'No se pudo actualizar la materia prima STD.')
    } finally {
      setStdEditLoading(false)
    }
  }

  const toggleIreksActive = async () => {
    const detail = ireksDetailQuery.data.detail
    if (!detail || detail.id === null || ireksActiveLoading) {
      return
    }
    const nextActive = !detail.articulo_status_activo
    setIreksActiveLoading(true)
    setIreksActiveError('')
    setIreksActiveMessage('')
    try {
      await updateIreksIngredient(detail.id, { articulo_status_activo: nextActive })
      await Promise.all([ireksQuery.reload(), ireksDetailQuery.reload()])
      setIreksActiveMessage(nextActive ? 'Ingrediente IREKS activado.' : 'Ingrediente IREKS desactivado.')
    } catch (error: unknown) {
      setIreksActiveError(error instanceof Error ? error.message : 'No se pudo actualizar el estado IREKS.')
    } finally {
      setIreksActiveLoading(false)
    }
  }

  const toggleIreksInList = async () => {
    const detail = ireksDetailQuery.data.detail
    if (!detail || detail.id === null || ireksListLoading) {
      return
    }
    const nextInList = !detail.articulo_status_en_lista
    setIreksListLoading(true)
    setIreksListError('')
    setIreksListMessage('')
    try {
      await updateIreksIngredient(detail.id, { articulo_status_en_lista: nextInList })
      await Promise.all([ireksQuery.reload(), ireksDetailQuery.reload()])
      setIreksListMessage(nextInList ? 'Ingrediente IREKS marcado en lista.' : 'Ingrediente IREKS marcado fuera de lista.')
    } catch (error: unknown) {
      setIreksListError(error instanceof Error ? error.message : 'No se pudo actualizar el estado en lista.')
    } finally {
      setIreksListLoading(false)
    }
  }

  const removeIreks = async () => {
    const detail = ireksDetailQuery.data.detail
    if (!detail || detail.id === null || ireksDeleteLoading) {
      return
    }
    const confirmed = window.confirm(
      `Se eliminara el ingrediente IREKS ${detail.articulo_referencia || detail.articulo_id}. Esta accion no se puede deshacer.`,
    )
    if (!confirmed) {
      return
    }
    setIreksDeleteLoading(true)
    setIreksDeleteError('')
    setIreksDeleteMessage('')
    try {
      await deleteIreksIngredient(detail.id)
      setSelectedIreksCandidateId('')
      await Promise.all([ireksQuery.reload(), ireksDetailQuery.reload()])
      setIreksDeleteMessage('Ingrediente IREKS eliminado correctamente.')
    } catch (error: unknown) {
      setIreksDeleteError(error instanceof Error ? error.message : 'No se pudo eliminar el ingrediente IREKS.')
    } finally {
      setIreksDeleteLoading(false)
    }
  }

  const removeStd = async () => {
    const detail = stdDetailQuery.data.detail
    if (!detail || stdDeleteLoading) {
      return
    }
    const confirmed = window.confirm(
      `Se eliminara la materia prima ${detail.articulo_referencia_distribuidor || detail.articulo_id}. Esta accion no se puede deshacer.`,
    )
    if (!confirmed) {
      return
    }
    setStdDeleteLoading(true)
    setStdDeleteError('')
    setStdDeleteMessage('')
    try {
      await deleteStdIngredient(detail.articulo_id)
      setSelectedStdCandidateId('')
      setStdEditTargetId('')
      setStdEditForm(EMPTY_STD_EDIT_FORM)
      await Promise.all([stdQuery.reload(), stdDetailQuery.reload()])
      setStdDeleteMessage('Materia prima STD eliminada correctamente.')
    } catch (error: unknown) {
      setStdDeleteError(error instanceof Error ? error.message : 'No se pudo eliminar la materia prima STD.')
    } finally {
      setStdDeleteLoading(false)
    }
  }

  const saveIreksEdition = async () => {
    const detail = ireksDetailQuery.data.detail
    if (!detail || detail.id === null || ireksEditLoading) {
      return
    }
    if (!currentIreksEditForm.articulo_descripcion.trim()) {
      setIreksEditError('La descripcion es obligatoria.')
      setIreksEditMessage('')
      return
    }
    setIreksEditLoading(true)
    setIreksEditError('')
    setIreksEditMessage('')
    try {
      const updated = await updateIreksIngredient(detail.id, {
        articulo_referencia: currentIreksEditForm.articulo_referencia.trim(),
        articulo_referencia_corta: currentIreksEditForm.articulo_referencia_corta.trim(),
        articulo_descripcion: currentIreksEditForm.articulo_descripcion.trim(),
        categoria: currentIreksEditForm.categoria.trim(),
      })
      await Promise.all([ireksQuery.reload(), ireksDetailQuery.reload()])
      setIreksEditTargetId(updated.articulo_id)
      setIreksEditForm({
        articulo_referencia: updated.articulo_referencia || '',
        articulo_referencia_corta: updated.articulo_referencia_corta || '',
        articulo_descripcion: updated.articulo_descripcion || '',
        categoria: updated.categoria || '',
      })
      setIreksEditMessage('Ingrediente IREKS actualizado.')
    } catch (error: unknown) {
      setIreksEditError(error instanceof Error ? error.message : 'No se pudo actualizar el ingrediente IREKS.')
    } finally {
      setIreksEditLoading(false)
    }
  }

  const resetIreksTarifaForm = () => {
    setSelectedIreksTarifaId(null)
    setIreksTarifaForm(EMPTY_IREKS_TARIFA_FORM)
  }

  const onSelectIreksTarifa = (tarifa: TarifaPrecioIreksRead) => {
    setSelectedIreksTarifaId(tarifa.id ?? null)
    setIreksTarifaForm({
      tarifa_ano: String(tarifa.tarifa_ano ?? ''),
      precio_fabricante: String(tarifa.precio_fabricante ?? 0),
      precio_distribuidor: String(tarifa.precio_distribuidor ?? 0),
      descuento_pct: String(tarifa.descuento_pct ?? 0),
    })
    setIreksTarifaMessage('')
    setIreksTarifaError('')
  }

  const saveIreksTarifa = async () => {
    const detail = ireksDetailQuery.data.detail
    if (!detail || ireksTarifaLoading) {
      return
    }
    const year = Number.parseInt(ireksTarifaForm.tarifa_ano, 10)
    const fabricante = Number.parseFloat(ireksTarifaForm.precio_fabricante.replace(',', '.'))
    const distribuidor = Number.parseFloat(ireksTarifaForm.precio_distribuidor.replace(',', '.'))
    const descuento = Number.parseFloat(ireksTarifaForm.descuento_pct.replace(',', '.'))

    if (!Number.isFinite(year) || year <= 0) {
      setIreksTarifaError('El ano de tarifa debe ser numerico y mayor que 0.')
      setIreksTarifaMessage('')
      return
    }
    if (!Number.isFinite(fabricante) || !Number.isFinite(distribuidor) || !Number.isFinite(descuento)) {
      setIreksTarifaError('Precios y descuento deben ser valores numericos validos.')
      setIreksTarifaMessage('')
      return
    }

    setIreksTarifaLoading(true)
    setIreksTarifaError('')
    setIreksTarifaMessage('')
    try {
      const payload = {
        tarifa_ano: year,
        precio_fabricante: fabricante,
        precio_distribuidor: distribuidor,
        descuento_pct: descuento,
      }
      const saved = selectedIreksTarifa && selectedIreksTarifa.id !== null
        ? await updateIreksTarifa(selectedIreksTarifa.id, payload)
        : await createIreksTarifa({
          articulo_id: detail.articulo_id,
          ...payload,
        })
      await ireksDetailQuery.reload()
      setSelectedIreksTarifaId(saved.id ?? null)
      setIreksTarifaForm({
        tarifa_ano: String(saved.tarifa_ano ?? ''),
        precio_fabricante: String(saved.precio_fabricante ?? 0),
        precio_distribuidor: String(saved.precio_distribuidor ?? 0),
        descuento_pct: String(saved.descuento_pct ?? 0),
      })
      setIreksTarifaMessage(selectedIreksTarifa ? 'Tarifa actualizada.' : 'Tarifa creada.')
    } catch (error: unknown) {
      setIreksTarifaError(error instanceof Error ? error.message : 'No se pudo guardar la tarifa IREKS.')
    } finally {
      setIreksTarifaLoading(false)
    }
  }

  const removeIreksTarifa = async () => {
    if (!selectedIreksTarifa || selectedIreksTarifa.id === null || ireksTarifaLoading) {
      return
    }
    const confirmed = window.confirm('Se eliminara la tarifa seleccionada. Esta accion no se puede deshacer.')
    if (!confirmed) {
      return
    }
    setIreksTarifaLoading(true)
    setIreksTarifaError('')
    setIreksTarifaMessage('')
    try {
      await deleteIreksTarifa(selectedIreksTarifa.id)
      await ireksDetailQuery.reload()
      resetIreksTarifaForm()
      setIreksTarifaMessage('Tarifa eliminada.')
    } catch (error: unknown) {
      setIreksTarifaError(error instanceof Error ? error.message : 'No se pudo eliminar la tarifa IREKS.')
    } finally {
      setIreksTarifaLoading(false)
    }
  }

  return (
    <section className="page-grid">
      <div className="segmented">
        <button
          type="button"
          className={`segment-btn ${mode === 'ireks' ? 'active' : ''}`}
          onClick={() => setMode('ireks')}
        >
          IREKS
        </button>
        <button
          type="button"
          className={`segment-btn ${mode === 'std' ? 'active' : ''}`}
          onClick={() => setMode('std')}
        >
          STD
        </button>
      </div>

      <div className="toolbar">
        <input
          className="input"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={mode === 'ireks' ? 'Buscar por referencia, descripcion o almacen' : 'Buscar por referencia o descripcion de materia prima'}
        />
        <select
          className="select"
          value={activityFilter}
          onChange={(event) => setActivityFilter(event.target.value)}
        >
          <option value="all">Todos</option>
          <option value="active">Activos</option>
          <option value="inactive">Inactivos</option>
        </select>
      </div>

      <div className="cards">
        <StatCard label="Total IREKS" value={totals.ireksTotal} />
        <StatCard label="IREKS activos" value={totals.ireksActive} />
        <StatCard label="Total STD" value={totals.stdTotal} />
        <StatCard label="STD activos" value={totals.stdActive} />
      </div>

      {mode === 'ireks' && (
        <>
          <QueryState
            loading={ireksQuery.loading}
            error={ireksQuery.error}
            empty={!ireksQuery.data.rows.length}
            emptyMessage="No hay ingredientes IREKS para los filtros actuales."
          />

          {!!ireksQuery.data.rows.length && (
            <div className="split-panel">
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Referencia</th>
                      <th>Descripcion</th>
                      <th>Articulo ID</th>
                      <th>Peso envase total</th>
                      <th>Categoria</th>
                      <th>Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ireksQuery.data.rows.map((row) => (
                      <tr
                        key={`${row.id ?? row.articulo_id}`}
                        className={row.articulo_id === selectedIreks?.articulo_id ? 'row-selected' : ''}
                        onClick={() => {
                          setSelectedIreksCandidateId(row.articulo_id)
                          setIreksEditTargetId(row.articulo_id)
                          setIreksEditForm({
                            articulo_referencia: row.articulo_referencia || '',
                            articulo_referencia_corta: row.articulo_referencia_corta || '',
                            articulo_descripcion: row.articulo_descripcion || '',
                            categoria: row.categoria || '',
                          })
                        }}
                      >
                        <td>{row.articulo_referencia || '-'}</td>
                        <td>{row.articulo_descripcion || '-'}</td>
                        <td>{row.articulo_id || '-'}</td>
                        <td>{formatWeight(row.articulo_envase_peso_total)}</td>
                        <td>{row.categoria || '-'}</td>
                        <td>
                          <span className={`pill ${row.articulo_status_activo ? 'ok' : 'off'}`}>
                            {row.articulo_status_activo ? 'Activo' : 'Inactivo'}
                          </span>{' '}
                          <span className={`pill ${row.articulo_status_en_lista ? 'warn' : 'off'}`}>
                            {row.articulo_status_en_lista ? 'En lista' : 'Fuera lista'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <aside className="detail-panel">
                <QueryState
                  loading={ireksDetailQuery.loading}
                  error={ireksDetailQuery.error}
                  empty={!ireksDetailQuery.data.detail}
                  emptyMessage="Selecciona un ingrediente IREKS para ver detalle."
                />

                {!!ireksDetailQuery.data.detail && (
                  <>
                    <dl className="detail-list">
                      <div>
                        <dt>Referencia corta</dt>
                        <dd>{ireksDetailQuery.data.detail.articulo_referencia_corta || '-'}</dd>
                      </div>
                      <div>
                        <dt>Fabricante ID</dt>
                        <dd>{ireksDetailQuery.data.detail.fabricante_id || '-'}</dd>
                      </div>
                      <div>
                        <dt>Distribuidor ID</dt>
                        <dd>{ireksDetailQuery.data.detail.distribuidor_id || '-'}</dd>
                      </div>
                      <div>
                        <dt>Formato envase</dt>
                        <dd>
                          {formatWeight(ireksDetailQuery.data.detail.articulo_envase_cantidad)} x {formatWeight(ireksDetailQuery.data.detail.articulo_envase_peso)}{' '}
                          {ireksDetailQuery.data.detail.articulo_envase_unidad_medida || '-'}
                        </dd>
                      </div>
                    </dl>

                    <div className="related-block">
                      <h3>Edicion rapida IREKS</h3>
                      <div className="form-grid">
                        <label>
                          Referencia
                          <input
                            className="input"
                            value={currentIreksEditForm.articulo_referencia}
                            onChange={(event) => {
                              if (ireksDetailQuery.data.detail) {
                                setIreksEditTargetId(ireksDetailQuery.data.detail.articulo_id)
                              }
                              setIreksEditForm((prev) => ({ ...prev, articulo_referencia: event.target.value }))
                            }}
                            disabled={ireksEditLoading || ireksActiveLoading || ireksListLoading || ireksDeleteLoading}
                          />
                        </label>
                        <label>
                          Referencia corta
                          <input
                            className="input"
                            value={currentIreksEditForm.articulo_referencia_corta}
                            onChange={(event) => {
                              if (ireksDetailQuery.data.detail) {
                                setIreksEditTargetId(ireksDetailQuery.data.detail.articulo_id)
                              }
                              setIreksEditForm((prev) => ({ ...prev, articulo_referencia_corta: event.target.value }))
                            }}
                            disabled={ireksEditLoading || ireksActiveLoading || ireksListLoading || ireksDeleteLoading}
                          />
                        </label>
                        <label>
                          Descripcion
                          <input
                            className="input"
                            value={currentIreksEditForm.articulo_descripcion}
                            onChange={(event) => {
                              if (ireksDetailQuery.data.detail) {
                                setIreksEditTargetId(ireksDetailQuery.data.detail.articulo_id)
                              }
                              setIreksEditForm((prev) => ({ ...prev, articulo_descripcion: event.target.value }))
                            }}
                            disabled={ireksEditLoading || ireksActiveLoading || ireksListLoading || ireksDeleteLoading}
                          />
                        </label>
                        <label>
                          Categoria
                          <input
                            className="input"
                            value={currentIreksEditForm.categoria}
                            onChange={(event) => {
                              if (ireksDetailQuery.data.detail) {
                                setIreksEditTargetId(ireksDetailQuery.data.detail.articulo_id)
                              }
                              setIreksEditForm((prev) => ({ ...prev, categoria: event.target.value }))
                            }}
                            disabled={ireksEditLoading || ireksActiveLoading || ireksListLoading || ireksDeleteLoading}
                          />
                        </label>
                      </div>
                      <div className="toolbar">
                        <button
                          type="button"
                          className="action-btn"
                          onClick={saveIreksEdition}
                          disabled={ireksEditLoading || ireksActiveLoading || ireksListLoading || ireksDeleteLoading}
                        >
                          {ireksEditLoading ? 'Guardando...' : 'Guardar cambios IREKS'}
                        </button>
                      </div>
                      {!!ireksEditMessage && <div className="state">{ireksEditMessage}</div>}
                      {!!ireksEditError && <div className="state">Error: {ireksEditError}</div>}
                    </div>

                    <div className="related-block">
                      <button
                        type="button"
                        className="action-btn"
                        disabled={ireksActiveLoading || ireksListLoading || ireksDeleteLoading || ireksEditLoading}
                        onClick={toggleIreksActive}
                      >
                        {ireksActiveLoading
                          ? 'Guardando...'
                          : ireksDetailQuery.data.detail.articulo_status_activo
                            ? 'Desactivar IREKS'
                            : 'Activar IREKS'}
                      </button>
                      {!!ireksActiveMessage && <div className="state">{ireksActiveMessage}</div>}
                      {!!ireksActiveError && <div className="state">Error: {ireksActiveError}</div>}
                    </div>

                    <div className="related-block">
                      <button
                        type="button"
                        className="action-btn"
                        disabled={ireksListLoading || ireksActiveLoading || ireksDeleteLoading || ireksEditLoading}
                        onClick={toggleIreksInList}
                      >
                        {ireksListLoading
                          ? 'Guardando...'
                          : ireksDetailQuery.data.detail.articulo_status_en_lista
                            ? 'Marcar fuera de lista'
                            : 'Marcar en lista'}
                      </button>
                      {!!ireksListMessage && <div className="state">{ireksListMessage}</div>}
                      {!!ireksListError && <div className="state">Error: {ireksListError}</div>}
                    </div>

                    <div className="related-block">
                      <button
                        type="button"
                        className="action-btn"
                        disabled={ireksDeleteLoading || ireksListLoading || ireksActiveLoading || ireksEditLoading}
                        onClick={removeIreks}
                      >
                        {ireksDeleteLoading ? 'Eliminando...' : 'Eliminar IREKS'}
                      </button>
                      {!!ireksDeleteMessage && <div className="state">{ireksDeleteMessage}</div>}
                      {!!ireksDeleteError && <div className="state">Error: {ireksDeleteError}</div>}
                    </div>

                    {!!ireksDetailQuery.data.nutrition && (
                      <div className="related-block">
                        <h3>Nutricion</h3>
                        <div className="mini-grid">
                          <span>Kcal: {formatWeight(ireksDetailQuery.data.nutrition.energia_kcal)}</span>
                          <span>Proteinas: {formatWeight(ireksDetailQuery.data.nutrition.proteinas_g)}</span>
                          <span>Hidratos: {formatWeight(ireksDetailQuery.data.nutrition.hidratos_g)}</span>
                          <span>Sal: {formatWeight(ireksDetailQuery.data.nutrition.sal_g)}</span>
                        </div>
                      </div>
                    )}

                    <div className="related-block">
                      <h3>Tarifas</h3>
                      {!ireksDetailQuery.data.tarifas.length && <div className="state">Sin tarifas registradas.</div>}
                      {!!ireksDetailQuery.data.tarifas.length && (
                        <div className="table-wrap">
                          <table>
                            <thead>
                              <tr>
                                <th>Ano</th>
                                <th>Fabricante</th>
                                <th>Distribuidor</th>
                                <th>Dto %</th>
                              </tr>
                            </thead>
                            <tbody>
                              {ireksDetailQuery.data.tarifas.slice(0, 8).map((tarifa) => (
                                <tr
                                  key={tarifa.id ?? `${tarifa.articulo_id}-${tarifa.tarifa_ano}`}
                                  className={tarifa.id !== null && tarifa.id === selectedIreksTarifaId ? 'row-selected' : ''}
                                  onClick={() => onSelectIreksTarifa(tarifa)}
                                >
                                  <td>{tarifa.tarifa_ano}</td>
                                  <td>{formatWeight(tarifa.precio_fabricante)}</td>
                                  <td>{formatWeight(tarifa.precio_distribuidor)}</td>
                                  <td>{formatWeight(tarifa.descuento_pct)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                      <div className="form-grid">
                        <label>
                          Ano
                          <input
                            className="input"
                            value={ireksTarifaForm.tarifa_ano}
                            onChange={(event) =>
                              setIreksTarifaForm((prev) => ({ ...prev, tarifa_ano: event.target.value }))
                            }
                            disabled={ireksTarifaLoading}
                            placeholder="Ej: 2026"
                          />
                        </label>
                        <label>
                          Precio fabricante
                          <input
                            className="input"
                            value={ireksTarifaForm.precio_fabricante}
                            onChange={(event) =>
                              setIreksTarifaForm((prev) => ({ ...prev, precio_fabricante: event.target.value }))
                            }
                            disabled={ireksTarifaLoading}
                          />
                        </label>
                        <label>
                          Precio distribuidor
                          <input
                            className="input"
                            value={ireksTarifaForm.precio_distribuidor}
                            onChange={(event) =>
                              setIreksTarifaForm((prev) => ({ ...prev, precio_distribuidor: event.target.value }))
                            }
                            disabled={ireksTarifaLoading}
                          />
                        </label>
                        <label>
                          Descuento %
                          <input
                            className="input"
                            value={ireksTarifaForm.descuento_pct}
                            onChange={(event) =>
                              setIreksTarifaForm((prev) => ({ ...prev, descuento_pct: event.target.value }))
                            }
                            disabled={ireksTarifaLoading}
                          />
                        </label>
                      </div>
                      <div className="toolbar">
                        <button
                          type="button"
                          className="action-btn"
                          onClick={saveIreksTarifa}
                          disabled={ireksTarifaLoading}
                        >
                          {ireksTarifaLoading ? 'Guardando...' : selectedIreksTarifa ? 'Actualizar tarifa' : 'Crear tarifa'}
                        </button>
                        <button
                          type="button"
                          className="action-btn"
                          onClick={removeIreksTarifa}
                          disabled={ireksTarifaLoading || !selectedIreksTarifa || selectedIreksTarifa.id === null}
                        >
                          {ireksTarifaLoading ? 'Eliminando...' : 'Eliminar tarifa'}
                        </button>
                        <button
                          type="button"
                          className="action-btn"
                          onClick={resetIreksTarifaForm}
                          disabled={ireksTarifaLoading}
                        >
                          Limpiar
                        </button>
                      </div>
                      {!!ireksTarifaMessage && <div className="state">{ireksTarifaMessage}</div>}
                      {!!ireksTarifaError && <div className="state">Error: {ireksTarifaError}</div>}
                    </div>
                  </>
                )}
              </aside>
            </div>
          )}
        </>
      )}

      {mode === 'std' && (
        <>
          <QueryState
            loading={stdQuery.loading}
            error={stdQuery.error}
            empty={!stdQuery.data.length}
            emptyMessage="No hay materias primas STD para los filtros actuales."
          />

          {!!stdQuery.data.length && (
            <div className="split-panel">
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Referencia</th>
                      <th>Descripcion</th>
                      <th>Formato</th>
                      <th>Categoria</th>
                      <th>PVP formato</th>
                      <th>Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stdQuery.data.map((row) => (
                      <tr
                        key={row.articulo_id}
                        className={row.articulo_id === selectedStd?.articulo_id ? 'row-selected' : ''}
                        onClick={() => {
                          setSelectedStdCandidateId(row.articulo_id)
                          setStdEditTargetId(row.articulo_id)
                          setStdEditForm({
                            articulo_descripcion: row.articulo_descripcion || '',
                            pvp_formato: String(row.pvp_formato ?? 0),
                            pvp_unidad_medida: String(row.pvp_unidad_medida ?? 0),
                          })
                        }}
                      >
                        <td>{row.articulo_referencia_distribuidor || '-'}</td>
                        <td>{row.articulo_descripcion || '-'}</td>
                        <td>
                          {formatWeight(row.formato_cantidad)} {row.formato_unidad || '-'}
                        </td>
                        <td>{row.categoria || '-'}</td>
                        <td>{formatWeight(row.pvp_formato)}</td>
                        <td>
                          <span className={`pill ${row.activo ? 'ok' : 'off'}`}>{row.activo ? 'Activo' : 'Inactivo'}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <aside className="detail-panel">
                <QueryState
                  loading={stdDetailQuery.loading}
                  error={stdDetailQuery.error}
                  empty={!stdDetailQuery.data.detail}
                  emptyMessage="Selecciona una materia prima para ver detalle."
                />

                {!!stdDetailQuery.data.detail && (
                  <>
                    <dl className="detail-list">
                      <div>
                        <dt>Proveedor ID</dt>
                        <dd>{stdDetailQuery.data.detail.proveedor_id || '-'}</dd>
                      </div>
                      <div>
                        <dt>Distribuidor</dt>
                        <dd>{stdDetailQuery.data.detail.distribuidor_nombre || stdDetailQuery.data.detail.distribuidor_id || '-'}</dd>
                      </div>
                      <div>
                        <dt>PVP unidad medida</dt>
                        <dd>{formatWeight(stdDetailQuery.data.detail.pvp_unidad_medida)}</dd>
                      </div>
                    </dl>

                    <div className="related-block">
                      <button
                        type="button"
                        className="action-btn"
                        disabled={stdActiveLoading || stdEditLoading || stdDeleteLoading}
                        onClick={toggleStdActive}
                      >
                        {stdActiveLoading
                          ? 'Guardando...'
                          : stdDetailQuery.data.detail.activo
                            ? 'Desactivar materia prima'
                            : 'Activar materia prima'}
                      </button>
                      {!!stdActiveMessage && <div className="state">{stdActiveMessage}</div>}
                      {!!stdActiveError && <div className="state">Error: {stdActiveError}</div>}
                    </div>

                    <div className="related-block">
                      <h3>Edicion rapida STD</h3>
                      <div className="form-grid">
                        <label>
                          Descripcion
                          <input
                            className="input"
                            value={currentStdEditForm.articulo_descripcion}
                            onChange={(event) => {
                              if (stdDetailQuery.data.detail) {
                                setStdEditTargetId(stdDetailQuery.data.detail.articulo_id)
                              }
                              setStdEditForm((prev) => ({ ...prev, articulo_descripcion: event.target.value }))
                            }}
                            disabled={stdEditLoading || stdActiveLoading}
                          />
                        </label>
                        <label>
                          PVP formato
                          <input
                            className="input"
                            value={currentStdEditForm.pvp_formato}
                            onChange={(event) => {
                              if (stdDetailQuery.data.detail) {
                                setStdEditTargetId(stdDetailQuery.data.detail.articulo_id)
                              }
                              setStdEditForm((prev) => ({ ...prev, pvp_formato: event.target.value }))
                            }}
                            disabled={stdEditLoading || stdActiveLoading}
                          />
                        </label>
                        <label>
                          PVP unidad medida
                          <input
                            className="input"
                            value={currentStdEditForm.pvp_unidad_medida}
                            onChange={(event) => {
                              if (stdDetailQuery.data.detail) {
                                setStdEditTargetId(stdDetailQuery.data.detail.articulo_id)
                              }
                              setStdEditForm((prev) => ({ ...prev, pvp_unidad_medida: event.target.value }))
                            }}
                            disabled={stdEditLoading || stdActiveLoading}
                          />
                        </label>
                      </div>
                      <div className="toolbar">
                        <button
                          type="button"
                          className="action-btn"
                          onClick={saveStdEdition}
                          disabled={stdEditLoading || stdActiveLoading || stdDeleteLoading}
                        >
                          {stdEditLoading ? 'Guardando...' : 'Guardar cambios STD'}
                        </button>
                        <button
                          type="button"
                          className="action-btn"
                          onClick={removeStd}
                          disabled={stdEditLoading || stdActiveLoading || stdDeleteLoading}
                        >
                          {stdDeleteLoading ? 'Eliminando...' : 'Eliminar STD'}
                        </button>
                      </div>
                      {!!stdEditMessage && <div className="state">{stdEditMessage}</div>}
                      {!!stdEditError && <div className="state">Error: {stdEditError}</div>}
                      {!!stdDeleteMessage && <div className="state">{stdDeleteMessage}</div>}
                      {!!stdDeleteError && <div className="state">Error: {stdDeleteError}</div>}
                    </div>

                    {!!stdDetailQuery.data.nutrition && (
                      <div className="related-block">
                        <h3>Nutricion</h3>
                        <div className="mini-grid">
                          <span>Kcal: {formatWeight(stdDetailQuery.data.nutrition.energia_kcal)}</span>
                          <span>Proteinas: {formatWeight(stdDetailQuery.data.nutrition.proteinas_g)}</span>
                          <span>Hidratos: {formatWeight(stdDetailQuery.data.nutrition.hidratos_g)}</span>
                          <span>Sal: {formatWeight(stdDetailQuery.data.nutrition.sal_g)}</span>
                        </div>
                      </div>
                    )}

                    <div className="related-block">
                      <h3>Historico de precios</h3>
                      {!stdDetailQuery.data.prices.length && <div className="state">Sin historico de precios.</div>}
                      {!!stdDetailQuery.data.prices.length && (
                        <div className="table-wrap">
                          <table>
                            <thead>
                              <tr>
                                <th>Fecha</th>
                                <th>Costo neto</th>
                              </tr>
                            </thead>
                            <tbody>
                              {stdDetailQuery.data.prices.slice(0, 8).map((price) => (
                                <tr key={price.id ?? `${price.articulo_id}-${price.fecha_precio}`}>
                                  <td>{price.fecha_precio}</td>
                                  <td>{formatWeight(price.costo_neto)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  </>
                )}
              </aside>
            </div>
          )}
        </>
      )}
    </section>
  )
}
