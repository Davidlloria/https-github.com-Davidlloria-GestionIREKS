import { useCallback, useMemo, useState } from 'react'
import {
  getIreksIngredientDetail,
  getIreksNutrition,
  getStdIngredientDetail,
  getStdNutrition,
  listIreksIngredients,
  listIreksTarifas,
  listStdIngredients,
  listStdPrices,
  updateStdActive,
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

export function IngredientsPage() {
  const [mode, setMode] = useState<IngredientMode>('ireks')
  const [search, setSearch] = useState('')
  const [activityFilter, setActivityFilter] = useState('all')
  const [selectedIreksCandidateId, setSelectedIreksCandidateId] = useState('')
  const [selectedStdCandidateId, setSelectedStdCandidateId] = useState('')
  const [stdActiveLoading, setStdActiveLoading] = useState(false)
  const [stdActiveMessage, setStdActiveMessage] = useState('')
  const [stdActiveError, setStdActiveError] = useState('')

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
                        onClick={() => setSelectedIreksCandidateId(row.articulo_id)}
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
                                <tr key={tarifa.id ?? `${tarifa.articulo_id}-${tarifa.tarifa_ano}`}>
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
                        onClick={() => setSelectedStdCandidateId(row.articulo_id)}
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
                        disabled={stdActiveLoading}
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
