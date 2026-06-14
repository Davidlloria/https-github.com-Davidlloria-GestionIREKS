import { useState } from 'react'

interface ConfigurationPageProps {
  onBack: () => void
}

type ConfigTabKey = 'export' | 'import' | 'maintenance' | 'api' | 'mail' | 'aux'

const CONFIG_TABS: Array<{ key: ConfigTabKey; label: string }> = [
  { key: 'export', label: 'Exportación BD' },
  { key: 'import', label: 'Importación BD' },
  { key: 'maintenance', label: 'Mantenimiento BD' },
  { key: 'api', label: 'API' },
  { key: 'mail', label: 'Correo' },
  { key: 'aux', label: 'Auxiliares' },
]

const CONFIG_TAB_CONTENT: Record<
  ConfigTabKey,
  {
    title: string
    description: string
    badges: string[]
    notes: string[]
  }
> = {
  export: {
    title: 'Exportación BD',
    description: 'Maqueta visual de la consola de exportación. Las exportaciones reales quedan bloqueadas en este corte.',
    badges: ['Clientes', 'Contactos', 'Técnicos', 'Distribuidores', 'Colaboradores', 'Cursos', 'Fórmulas', 'Almacén', 'Productos IREKS', 'Materias primas', 'Pedidos', 'Ventas', 'Configuración'],
    notes: [
      'No se ejecuta ninguna exportación.',
      'La selección de módulos se muestra solo como referencia visual.',
      'Las rutas de salida y el botón Exportar permanecen deshabilitados.',
    ],
  },
  import: {
    title: 'Importación BD',
    description: 'Sección reservada para futuras importaciones controladas. No se procesa ningún fichero.',
    badges: ['Importaciones pendientes', 'Sin ejecución'],
    notes: [
      'No se permite subir ficheros.',
      'No se procesan importaciones masivas.',
      'El comportamiento real queda pospuesto a un corte posterior.',
    ],
  },
  maintenance: {
    title: 'Mantenimiento BD',
    description: 'Panel de mantenimiento bloqueado para evitar acciones destructivas o de alto impacto.',
    badges: ['Integridad', 'Backups', 'Reparaciones', 'Optimización'],
    notes: [
      'Integridad, backup y reparaciones permanecen bloqueados.',
      'No se ejecuta ninguna operación de mantenimiento.',
      'Las acciones reales exigirán revisión previa de permisos.',
    ],
  },
  api: {
    title: 'API',
    description: 'Configuración técnica reservada. En este corte solo se presenta como referencia.',
    badges: ['Proveedores', 'JSON', 'Claves', 'Conexión'],
    notes: [
      'No se guardan parámetros.',
      'No se editan proveedores.',
      'La integración real quedará para una fase posterior.',
    ],
  },
  mail: {
    title: 'Correo',
    description: 'Zona controlada para parámetros de correo de pedidos. Sin envío ni persistencia en este corte.',
    badges: ['orders_mail', 'Destino', 'Histórico'],
    notes: [
      'No se envían correos.',
      'No se guarda configuración de salida.',
      'Solo se muestra el bloque visual de referencia.',
    ],
  },
  aux: {
    title: 'Auxiliares',
    description: 'Bloque auxiliar para catálogos y utilidades visuales sin acciones reales.',
    badges: ['Catálogos', 'Utilidades', 'Pendiente'],
    notes: [
      'No hay acciones ejecutables.',
      'Solo se reserva el espacio visual.',
      'La funcionalidad concreta se definirá más adelante.',
    ],
  },
}

const blockedActions = [
  'Exportar BD',
  'Importar BD',
  'Mantenimiento BD',
  'Backup',
  'Integridad',
  'Guardar API',
  'Guardar correo',
  'Importar pedidos',
]

function ConfigGearIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3.2" />
      <path d="M19 12a7 7 0 0 0-.08-1l1.76-1.36-1.9-3.29-2.12.72a7 7 0 0 0-1.73-1l-.32-2.19h-3.8l-.32 2.2a7 7 0 0 0-1.73 1l-2.12-.73-1.9 3.29L5.08 11A7 7 0 0 0 5 12c0 .34.03.67.08 1l-1.76 1.36 1.9 3.29 2.12-.72a7 7 0 0 0 1.73 1l.32 2.19h3.8l.32-2.2a7 7 0 0 0 1.73-1l2.12.73 1.9-3.29L18.92 13c.05-.33.08-.66.08-1Z" />
    </svg>
  )
}

export function ConfigurationPage({ onBack }: ConfigurationPageProps) {
  const [activeTab, setActiveTab] = useState<ConfigTabKey>('export')

  const currentTab = CONFIG_TAB_CONTENT[activeTab]

  return (
    <section className="configuration-page">
      <header className="configuration-header">
        <div className="configuration-header-copy">
          <p className="configuration-kicker">CONFIGURACIÓN</p>
          <h2>Configuración</h2>
          <p className="configuration-subtitle">
            Acceso controlado desde Dashboard. Esta pantalla es read-only y no ejecuta exportaciones,
            importaciones ni mantenimiento.
          </p>
        </div>

        <button type="button" className="surface-chip configuration-back-button" onClick={onBack}>
          Volver al inicio
        </button>
      </header>

      <div className="configuration-summary">
        <article className="configuration-summary-card">
          <span className="configuration-summary-icon" aria-hidden="true">
            <ConfigGearIcon />
          </span>
          <div>
            <strong>Vista controlada</strong>
            <p>No hay mutaciones ni accesos a escritura activos en este corte.</p>
          </div>
        </article>

        <article className="configuration-summary-card">
          <span className="configuration-summary-icon configuration-summary-icon-muted" aria-hidden="true">
            <ConfigGearIcon />
          </span>
          <div>
            <strong>Acceso desde Dashboard</strong>
            <p>La entrada aparece solo en Accesos rápidos, no en la barra superior.</p>
          </div>
        </article>
      </div>

      <div className="configuration-tabs" role="tablist" aria-label="Secciones de configuración">
        {CONFIG_TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.key}
            className={`configuration-tab ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="configuration-workspace">
        <article className="configuration-panel configuration-main-panel">
          <div className="section-heading section-heading-compact">
            <div>
              <h3>{currentTab.title}</h3>
              <p>{currentTab.description}</p>
            </div>
            <span className="surface-chip">{currentTab.badges.length} referencias</span>
          </div>

          <div className="configuration-note">
            <strong>Vista de referencia</strong>
            <p>
              El contenido se presenta como maqueta visual para reservar el espacio funcional de
              la pantalla de Configuración sin exponer acciones activas.
            </p>
          </div>

          <div className="configuration-chip-list" aria-label={currentTab.title}>
            {currentTab.badges.map((badge) => (
              <span key={badge} className="configuration-chip">
                {badge}
              </span>
            ))}
          </div>

          <div className="toolbar">
            <button type="button" className="action-btn" disabled>
              Acción bloqueada
            </button>
            <button type="button" className="action-btn" disabled>
              Exportar
            </button>
            <button type="button" className="action-btn" disabled>
              Importar
            </button>
          </div>
        </article>

        <article className="configuration-panel configuration-side-panel">
          <div className="section-heading section-heading-compact">
            <div>
              <h3>Bloqueos activos</h3>
              <p>Acciones que permanecen deshabilitadas en este corte.</p>
            </div>
          </div>

          <div className="configuration-block-list" aria-label="Acciones bloqueadas">
            {blockedActions.map((action) => (
              <div key={action} className="configuration-block-item">
                <span>{action}</span>
                <strong>No disponible</strong>
              </div>
            ))}
          </div>

          <div className="configuration-note configuration-note-soft">
            <strong>Estado actual</strong>
            <p>
              La pantalla es una entrada controlada desde el Dashboard. La funcionalidad operativa
              completa se pospone a una fase posterior.
            </p>
          </div>
        </article>
      </div>
    </section>
  )
}
