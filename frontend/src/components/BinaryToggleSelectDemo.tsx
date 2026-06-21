import { useState } from 'react'
import { BinaryToggleSelect } from './BinaryToggleSelect'

export function BinaryToggleSelectDemo() {
  const [isActive, setIsActive] = useState(true)
  const [allowsSale, setAllowsSale] = useState(false)

  return (
    <div className="binary-toggle-select-demo">
      <BinaryToggleSelect
        value={isActive}
        onChange={setIsActive}
        trueLabel="Activo"
        falseLabel="Inactivo"
        ariaLabel="Estado activo del producto"
      />
      <BinaryToggleSelect
        value={allowsSale}
        onChange={setAllowsSale}
        trueLabel="Sí"
        falseLabel="No"
        ariaLabel="Permite venta"
      />
      <BinaryToggleSelect
        value={false}
        onChange={() => {}}
        trueLabel="Visible"
        falseLabel="Oculto"
        disabled
        ariaLabel="Visibilidad"
      />
    </div>
  )
}
