from __future__ import annotations
# pyright: reportIncompatibleVariableOverride=false

from datetime import date, datetime
from typing import ClassVar, Optional
from uuid import uuid4

from sqlalchemy import ForeignKeyConstraint
from sqlmodel import Field, SQLModel


class TimeStampedModel(SQLModel):
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class Cliente(SQLModel, table=True):
    __tablename__: ClassVar[str] = "clientes"

    cliente_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    cliente_codigo: int = Field(default=0, index=True, unique=True, nullable=False)
    cliente_nombre_comercial: str = Field(default="", max_length=255)
    cliente_nombre_fiscal: str = Field(default="", max_length=255)
    cliente_nombre_interno: str = Field(default="", max_length=255)
    cliente_abreviatura: str = Field(default="", max_length=20)
    cliente_cif: str = Field(default="", max_length=50)
    cliente_telefono: str = Field(default="", max_length=50)
    cliente_email: str = Field(default="", max_length=255)
    cliente_direccion: str = Field(default="")
    cliente_direccion_cp: str = Field(default="", max_length=20)
    cliente_direccion_localidad_id: str = Field(default="", max_length=36)
    cliente_direccion_municipio_id: str = Field(default="", max_length=36)
    cliente_direccion_provincia_id: str = Field(default="", max_length=36)
    cliente_direccion_isla_id: str = Field(default="", max_length=36)
    cliente_tipo: str = Field(default="", max_length=100)
    cliente_grupo: str = Field(default="", max_length=100)
    cliente_prospeccion: bool = Field(default=False)
    distribuidor_id: str = Field(default="", max_length=36)
    activo: bool = Field(default=True)


class Distribuidor(SQLModel, table=True):
    __tablename__: ClassVar[str] = "distribuidores"

    distribuidor_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    distribuidor_codigo: int = Field(default=0, index=True, nullable=False)
    distribuidor_razon_social: str = Field(default="", max_length=255)
    distribuidor_nombre_comercial: str = Field(default="", max_length=255)
    distribuidor_cif: str = Field(default="", max_length=50)
    distribuidor_telefono: str = Field(default="", max_length=50)
    distribuidor_contacto: str = Field(default="", max_length=255)


class Proveedor(SQLModel, table=True):
    __tablename__: ClassVar[str] = "proveedores"

    proveedor_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    proveedor_codigo: int = Field(default=0, index=True, nullable=False)
    proveedor_razon_social: str = Field(default="", max_length=255)
    proveedor_nombre_comercial: str = Field(default="", max_length=255)
    proveedor_cif: str = Field(default="", max_length=50)
    proveedor_telefono: str = Field(default="", max_length=50)
    proveedor_contacto: str = Field(default="", max_length=255)

    # Compatibilidad temporal para UI/codigo legacy que aun usa "distribuidor_*".
    @property
    def distribuidor_id(self) -> str:
        return self.proveedor_id

    @property
    def distribuidor_codigo(self) -> int:
        return self.proveedor_codigo

    @property
    def distribuidor_razon_social(self) -> str:
        return self.proveedor_razon_social

    @property
    def distribuidor_nombre_comercial(self) -> str:
        return self.proveedor_nombre_comercial

    @property
    def distribuidor_cif(self) -> str:
        return self.proveedor_cif

    @property
    def distribuidor_telefono(self) -> str:
        return self.proveedor_telefono

    @property
    def distribuidor_contacto(self) -> str:
        return self.proveedor_contacto


class AlmacenMovimiento(SQLModel, table=True):
    __tablename__: ClassVar[str] = "almacen_movimientos"

    id: Optional[int] = Field(default=None, primary_key=True)
    almacen_id: str = Field(default="", nullable=False, max_length=36, index=True)
    articulo_id: str = Field(default="", nullable=False, max_length=36, index=True)
    pedido_numero: str = Field(default="", max_length=100, index=True)
    pedido_albaran_numero: str = Field(default="", max_length=100, index=True)
    cantidad: float = Field(default=0.0, nullable=False)
    articulo_lote: str = Field(default="", max_length=100, index=True)
    articulo_caducidad: Optional[date] = Field(default=None, nullable=True, index=True)
    fecha_pedido: date = Field(default_factory=date.today, nullable=False, index=True)
    albaran_item_id: str = Field(default="", max_length=36, index=True)


class AlmacenStock(SQLModel, table=True):
    __tablename__: ClassVar[str] = "almacen_stock"

    almacen_id: str = Field(primary_key=True, max_length=36)
    articulo_id: str = Field(primary_key=True, max_length=36)
    cantidad_total: float = Field(default=0.0, nullable=False)


class AlmacenCatalogo(SQLModel, table=True):
    __tablename__: ClassVar[str] = "almacenes_catalogo"

    almacen_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    almacen_nombre: str = Field(default="", max_length=255, index=True)


class InventarioCabecera(SQLModel, table=True):
    __tablename__: ClassVar[str] = "inventarios_cabecera"

    inventario_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    almacen_id: str = Field(default="", nullable=False, max_length=36, index=True)
    fecha: date = Field(default_factory=date.today, nullable=False, index=True)
    contador: str = Field(default="", max_length=120)
    aprobador: str = Field(default="", max_length=120)
    estado: str = Field(default="aprobado", max_length=30, index=True)
    lineas: int = Field(default=0)
    ajustes: int = Field(default=0)


class InventarioDetalle(SQLModel, table=True):
    __tablename__: ClassVar[str] = "inventarios_detalle"

    id: Optional[int] = Field(default=None, primary_key=True)
    inventario_id: str = Field(default="", nullable=False, max_length=36, index=True)
    almacen_id: str = Field(default="", nullable=False, max_length=36, index=True)
    articulo_id: str = Field(default="", nullable=False, max_length=36, index=True)
    articulo_lote: str = Field(default="", max_length=100, index=True)
    articulo_caducidad: Optional[date] = Field(default=None, nullable=True, index=True)
    teorico_uds: float = Field(default=0.0, nullable=False)
    conteo_uds: float = Field(default=0.0, nullable=False)
    diferencia_uds: float = Field(default=0.0, nullable=False)
    kg_ajuste: float = Field(default=0.0, nullable=False)


class Fabricante(SQLModel, table=True):
    __tablename__: ClassVar[str] = "fabricantes"

    fabricante_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    fabricante_codigo: int = Field(default=0, index=True)
    fabricante_nombre: str = Field(default="", nullable=False, max_length=255, index=True)


class Familia(SQLModel, table=True):
    __tablename__: ClassVar[str] = "familias"

    articulo_familia_id: str = Field(primary_key=True, max_length=36)
    fabricante_id: str = Field(nullable=False, max_length=36, index=True)
    articulo_familia_nombre: str = Field(default="", nullable=False, max_length=255, index=True)
    articulo_familia_codigo: str = Field(default="", nullable=False, max_length=100, index=True)


class Subfamilia(SQLModel, table=True):
    __tablename__: ClassVar[str] = "subfamilias"

    articulo_familia_id: str = Field(primary_key=True, max_length=36)
    articulo_subfamilia_id: str = Field(primary_key=True, max_length=36)
    articulo_subfamilia_nombre: str = Field(default="", nullable=False, max_length=255, index=True)
    articulo_subfamilia_codigo: str = Field(default="", nullable=False, max_length=100, index=True)


class Envase(SQLModel, table=True):
    __tablename__: ClassVar[str] = "envases"

    envase_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    envase_codigo: int = Field(default=0, index=True, nullable=False, unique=True)
    envase_nombre: str = Field(default="", nullable=False, max_length=255, index=True)


class Provincia(SQLModel, table=True):
    __tablename__: ClassVar[str] = "provincias"

    provincia_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    provincia_nombre: str = Field(default="", max_length=120)
    provincia_codigo: str = Field(default="", max_length=20, index=True, unique=True)


class Isla(SQLModel, table=True):
    __tablename__: ClassVar[str] = "islas"

    isla_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    provincia_id: str = Field(foreign_key="provincias.provincia_id", nullable=False, index=True, max_length=36)
    isla_nombre: str = Field(default="", max_length=120)
    isla_codigo: str = Field(default="", max_length=20, index=True, unique=True)
    isla_iniciales: str = Field(default="", max_length=12)


class Municipio(SQLModel, table=True):
    __tablename__: ClassVar[str] = "municipios"

    municipio_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    isla_id: str = Field(foreign_key="islas.isla_id", nullable=False, index=True, max_length=36)
    provincia_id: str = Field(default="", index=True, max_length=36)
    municipio_nombre: str = Field(default="", max_length=120)
    municipio_codigo: str = Field(default="", max_length=20, index=True, unique=True)


class CodigoPostal(SQLModel, table=True):
    __tablename__: ClassVar[str] = "codigos_postales"

    municipio_id: str = Field(
        primary_key=True,
        foreign_key="municipios.municipio_id",
        nullable=False,
        max_length=36,
    )
    codigo_postal: str = Field(default="", primary_key=True, max_length=20, index=True)


class Localidad(SQLModel, table=True):
    __tablename__: ClassVar[str] = "localidades"
    __table_args__ = (
        ForeignKeyConstraint(
            ["municipio_id", "codigo_postal"],
            ["codigos_postales.municipio_id", "codigos_postales.codigo_postal"],
        ),
    )

    localidad_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    municipio_id: str = Field(nullable=False, index=True, max_length=36)
    localidad_nombre: str = Field(default="", max_length=120)
    codigo_postal: Optional[str] = Field(default=None, nullable=True, index=True, max_length=20)


class TarifaPrecioIreks(SQLModel, table=True):
    __tablename__: ClassVar[str] = "tarifa_precios_ireks"

    id: Optional[int] = Field(default=None, primary_key=True)
    articulo_id: str = Field(default="", nullable=False, max_length=36, index=True)
    tarifa_ano: int = Field(default=0, nullable=False, index=True)
    precio_fabricante: float = Field(default=0.0, nullable=False)
    precio_distribuidor: float = Field(default=0.0, nullable=False)
    descuento_pct: float = Field(default=0.0, nullable=False)


class MateriaPrimaPrecio(SQLModel, table=True):
    __tablename__: ClassVar[str] = "materias_primas_precios"

    id: Optional[int] = Field(default=None, primary_key=True)
    articulo_id: str = Field(default="", nullable=False, max_length=36, index=True)
    fecha_precio: date = Field(nullable=False, index=True)
    costo_neto: float = Field(default=0.0, nullable=False)


class MateriaPrimaValorNutricional(SQLModel, table=True):
    __tablename__: ClassVar[str] = "productos_valores_nutricionales"

    articulo_id: str = Field(primary_key=True, max_length=36)
    energia_kj: float = Field(default=0.0, nullable=False)
    energia_kcal: float = Field(default=0.0, nullable=False)
    grasas_g: float = Field(default=0.0, nullable=False)
    saturadas_g: float = Field(default=0.0, nullable=False)
    hidratos_g: float = Field(default=0.0, nullable=False)
    azucares_g: float = Field(default=0.0, nullable=False)
    fibra_g: float = Field(default=0.0, nullable=False)
    proteinas_g: float = Field(default=0.0, nullable=False)
    sal_g: float = Field(default=0.0, nullable=False)


class IngredienteBase(SQLModel):
    codigo: str = Field(index=True, unique=True, max_length=50)
    nombre: str = Field(max_length=255)
    familia: str = Field(default="", max_length=100)
    subfamilia: str = Field(default="", max_length=100)
    marca: str = Field(default="", max_length=100)
    formato_envase: str = Field(default="", max_length=100)
    unidad_envase: str = Field(default="", max_length=20)
    cantidad_envase: float = Field(default=0.0)
    precio_unidad: float = Field(default=0.0)
    precio_kg: float = Field(default=0.0)
    es_harina: bool = Field(default=False)
    es_liquido: bool = Field(default=False)
    es_grasa: bool = Field(default=False)
    es_mejorante: bool = Field(default=False)
    activo: bool = Field(default=True)


class Contacto(TimeStampedModel, table=True):
    __tablename__: ClassVar[str] = "contactos"

    contacto_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    contacto_codigo: int = Field(default=0, index=True, unique=True, nullable=False)
    cliente_id: str = Field(index=True, foreign_key="clientes.cliente_id", nullable=False, max_length=36)
    nombre: str = Field(default="", max_length=255)
    apellidos: str = Field(default="", max_length=255)
    cargo: str = Field(default="", max_length=255)
    nif: str = Field(default="", max_length=50)
    telefono: str = Field(default="", max_length=50)
    email: str = Field(default="", max_length=255)


class Tecnico(TimeStampedModel, table=True):
    __tablename__: ClassVar[str] = "tecnicos"

    tecnico_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    tecnico_codigo: int = Field(default=0, index=True, unique=True, nullable=False)
    nombre: str = Field(default="", nullable=False, max_length=255)
    apellidos: str = Field(default="", max_length=255)
    movil: str = Field(default="", max_length=50)
    interno: str = Field(default="", max_length=20)
    email: str = Field(default="", max_length=255)


class Curso(TimeStampedModel, table=True):
    __tablename__: ClassVar[str] = "cursos"

    curso_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    curso_nombre: str = Field(default="", nullable=False, max_length=255)
    curso_fecha: date = Field(default_factory=date.today, nullable=False, index=True)
    invitacion: str = Field(default="")
    portada: str = Field(default="")
    recetario: str = Field(default="")


class Asistente(TimeStampedModel, table=True):
    __tablename__: ClassVar[str] = "asistentes"

    curso_id: str = Field(
        primary_key=True,
        foreign_key="cursos.curso_id",
        nullable=False,
        index=True,
        max_length=36,
    )
    contacto_id: str = Field(
        primary_key=True,
        foreign_key="contactos.contacto_id",
        nullable=False,
        index=True,
        max_length=36,
    )
    cliente_id: str = Field(
        foreign_key="clientes.cliente_id",
        nullable=False,
        index=True,
        max_length=36,
    )
    observaciones: str = Field(default="", nullable=False)
    status_confirmacion: bool = Field(default=False, nullable=False)


class CursoTecnico(TimeStampedModel, table=True):
    __tablename__: ClassVar[str] = "cursos_tecnicos"

    curso_id: str = Field(
        primary_key=True,
        foreign_key="cursos.curso_id",
        nullable=False,
        index=True,
        max_length=36,
    )
    tecnico_id: str = Field(
        primary_key=True,
        foreign_key="tecnicos.tecnico_id",
        nullable=False,
        index=True,
        max_length=36,
    )


class CursoDocumento(TimeStampedModel, table=True):
    __tablename__: ClassVar[str] = "cursos_documentos"

    curso_id: str = Field(
        primary_key=True,
        foreign_key="cursos.curso_id",
        nullable=False,
        max_length=36,
    )
    portada: str = Field(default="")
    invitacion: str = Field(default="")
    recetario: str = Field(default="")


class IngredienteIreks(SQLModel, table=True):
    __tablename__: ClassVar[str] = "productos_ireks"

    id: Optional[int] = Field(default=None, primary_key=True)
    almacen_id: str = Field(default="", nullable=False, max_length=36, index=True)
    fabricante_id: str = Field(default="", max_length=36, index=True)
    distribuidor_id: str = Field(default="", max_length=36, index=True)
    articulo_id: str = Field(default_factory=lambda: str(uuid4()), nullable=False, max_length=36, index=True)
    articulo_referencia: str = Field(default="", max_length=100, index=True)
    articulo_referencia_corta: str = Field(default="", max_length=100, index=True)
    articulo_descripcion: str = Field(default="", max_length=255, index=True)
    articulo_envase_id: str = Field(default="", max_length=36, index=True)
    articulo_contenido_unidad: str = Field(default="", max_length=50)
    articulo_envase_cantidad: float = Field(default=0.0)
    articulo_envase_peso: float = Field(default=0.0)
    articulo_envase_unidad_medida: str = Field(default="", max_length=20)
    articulo_envase_peso_total: float = Field(default=0.0)
    transporte_pallet_tipo: str = Field(default="", max_length=50)
    transporte_cajas_por_capa: float = Field(default=0.0)
    transporte_capas_por_pallet: float = Field(default=0.0)
    transporte_cajas_por_pallet: float = Field(default=0.0)
    transporte_unidades_por_pallet: float = Field(default=0.0)
    transporte_kg_por_pallet: float = Field(default=0.0)
    transporte_observaciones: str = Field(default="")
    articulo_familia_id: str = Field(default="", max_length=36, index=True)
    articulo_grupo_id: str = Field(default="", max_length=36, index=True)
    articulo_subfamilia_id: str = Field(default="", max_length=36, index=True)
    categoria: str = Field(default="", max_length=30, index=True)
    articulo_status_activo: bool = Field(default=True)
    articulo_status_en_lista: bool = Field(default=False)

    @property
    def codigo(self) -> str:
        return self.articulo_referencia

    @property
    def nombre(self) -> str:
        return self.articulo_descripcion

    @property
    def familia(self) -> str:
        return self.articulo_familia_id

    @property
    def subfamilia(self) -> str:
        return self.articulo_subfamilia_id

    @property
    def precio_kg(self) -> float:
        return 0.0

    @property
    def es_harina(self) -> bool:
        return (self.categoria or "").strip().lower() == "harina"

    @property
    def es_liquido(self) -> bool:
        return (self.categoria or "").strip().lower() == "liquido"


class IngredienteStd(SQLModel, table=True):
    __tablename__: ClassVar[str] = "materias_primas"

    articulo_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    articulo_referencia_distribuidor: str = Field(default="", max_length=100, index=True)
    proveedor_id: str = Field(default="", nullable=False, max_length=36, index=True)
    distribuidor_id: str = Field(default="", nullable=False, max_length=36, index=True)
    articulo_descripcion: str = Field(default="", nullable=False, max_length=255, index=True)
    articulo_grupo_id: str = Field(default="", max_length=36, index=True)
    articulo_familia_id: str = Field(default="", max_length=36, index=True)
    articulo_subfamilia_id: str = Field(default="", max_length=36, index=True)
    categoria: str = Field(default="", max_length=30, index=True)
    formato: str = Field(default="", max_length=100)
    formato_cantidad: float = Field(default=0.0)
    formato_unidad: str = Field(default="kg", max_length=20)
    pvp_formato: float = Field(default=0.0)
    pvp_unidad_medida: float = Field(default=0.0)
    activo: bool = Field(default=True)

    @property
    def id(self) -> str:
        return self.articulo_id

    @property
    def codigo(self) -> str:
        return self.articulo_referencia_distribuidor

    @codigo.setter
    def codigo(self, value: str) -> None:
        self.articulo_referencia_distribuidor = value

    @property
    def nombre(self) -> str:
        return self.articulo_descripcion

    @nombre.setter
    def nombre(self, value: str) -> None:
        self.articulo_descripcion = value

    @property
    def familia(self) -> str:
        return self.articulo_familia_id

    @property
    def subfamilia(self) -> str:
        return self.articulo_subfamilia_id

    @property
    def precio_kg(self) -> float:
        if self.pvp_unidad_medida <= 0:
            return 0.0
        unidad = (self.formato_unidad or "").strip().lower()
        if unidad == "kg":
            return self.pvp_unidad_medida
        if unidad == "g":
            return self.pvp_unidad_medida * 1000
        if unidad == "l":
            return self.pvp_unidad_medida
        if unidad == "ml":
            return self.pvp_unidad_medida * 1000
        return self.pvp_unidad_medida

    @property
    def es_harina(self) -> bool:
        return (self.categoria or "").strip().lower() == "harina"

    @property
    def es_liquido(self) -> bool:
        return (self.categoria or "").strip().lower() == "liquido"


class ReferenciaDistribuidor(SQLModel, table=True):
    __tablename__: ClassVar[str] = "referencias_distribuidor"

    articulo_id: str = Field(primary_key=True, max_length=36)
    distribuidor_id: str = Field(primary_key=True, max_length=36)
    articulo_referencia_distribuidor: str = Field(default="", max_length=100, index=True)
    articulo_descripcion_distribuidor: str = Field(default="", max_length=255, index=True)


class Pedido(SQLModel, table=True):
    __tablename__: ClassVar[str] = "pedidos"

    pedido_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    almacen_id: str = Field(default="", nullable=False, max_length=36, index=True)
    pedido_fecha: date = Field(default_factory=date.today, nullable=False, index=True)
    pedido_numero: str = Field(default="", max_length=100, index=True)
    pedido_albaran_numero: str = Field(default="", max_length=100, index=True)
    pedido_factura_numero: str = Field(default="", max_length=100, index=True)
    pedido_ref: str = Field(default="", max_length=255, index=True)
    pedido_estado: str = Field(default="", max_length=1, index=True)


class PedidoItem(SQLModel, table=True):
    __tablename__: ClassVar[str] = "pedidos_items"

    item_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    pedido_id: str = Field(foreign_key="pedidos.pedido_id", nullable=False, max_length=36, index=True)
    pedido_numero: str = Field(default="", max_length=100, index=True)
    pedido_albaran_numero: str = Field(default="", max_length=100, index=True)
    pedido_item_fecha: date = Field(default_factory=date.today, nullable=False, index=True)
    articulo_id: str = Field(nullable=False, max_length=36, index=True)
    articulo_cantidad: float = Field(default=0.0, nullable=False)


class Albaran(SQLModel, table=True):
    __tablename__: ClassVar[str] = "albaranes"

    albaran_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    almacen_id: str = Field(default="", nullable=False, max_length=36, index=True)
    pedido_id: str = Field(default="", nullable=False, max_length=36, index=True)
    albaran_numero: str = Field(default="", nullable=False, max_length=100, index=True)
    albaran_fecha: date = Field(default_factory=date.today, nullable=False, index=True)


class AlbaranItem(SQLModel, table=True):
    __tablename__: ClassVar[str] = "albaranes_items"

    item_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    pedido_id: str = Field(default="", nullable=False, max_length=36, index=True)
    albaran_id: str = Field(default="", nullable=False, max_length=36, index=True)
    albaran_numero: str = Field(default="", nullable=False, max_length=100, index=True)
    albaran_fecha: date = Field(default_factory=date.today, nullable=False, index=True)
    articulo_codigo: str = Field(default="", nullable=False, max_length=100, index=True)
    articulo_id: str = Field(default="", nullable=False, max_length=36, index=True)
    articulo_cantidad: float = Field(default=0.0, nullable=False)
    articulo_lote: str = Field(default="", max_length=100, index=True)
    articulo_caducidad: Optional[date] = Field(default=None, nullable=True, index=True)


class Factura(SQLModel, table=True):
    __tablename__: ClassVar[str] = "facturas"

    factura_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    almacen_id: str = Field(default="", nullable=False, max_length=36, index=True)
    pedido_id: str = Field(default="", nullable=False, max_length=36, index=True)
    factura_numero: str = Field(default="", nullable=False, max_length=100, index=True)
    factura_fecha: date = Field(default_factory=date.today, nullable=False, index=True)
    albaran_numero: str = Field(default="", max_length=100, index=True)
    factura_referencia: str = Field(default="", max_length=255, index=True)
    total_kilos: float = Field(default=0.0, nullable=False)
    importe_neto: float = Field(default=0.0, nullable=False)
    total_factura: float = Field(default=0.0, nullable=False)


class FacturaItem(SQLModel, table=True):
    __tablename__: ClassVar[str] = "facturas_items"

    item_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    pedido_id: str = Field(default="", nullable=False, max_length=36, index=True)
    factura_id: str = Field(default="", nullable=False, max_length=36, index=True)
    factura_numero: str = Field(default="", nullable=False, max_length=100, index=True)
    factura_fecha: date = Field(default_factory=date.today, nullable=False, index=True)
    albaran_numero: str = Field(default="", max_length=100, index=True)
    articulo_codigo: str = Field(default="", nullable=False, max_length=100, index=True)
    articulo_id: str = Field(default="", max_length=36, index=True)
    articulo_descripcion: str = Field(default="", max_length=255, index=True)
    articulo_cantidad: float = Field(default=0.0, nullable=False)
    articulo_envase: float = Field(default=0.0, nullable=False)
    articulo_kilos: float = Field(default=0.0, nullable=False)
    articulo_lote: str = Field(default="", max_length=100, index=True)
    articulo_caducidad: Optional[date] = Field(default=None, nullable=True, index=True)
    precio_unitario: float = Field(default=0.0, nullable=False)
    dto_pct: float = Field(default=20.0, nullable=False)
    iva_pct: float = Field(default=0.0, nullable=False)
    total_linea: float = Field(default=0.0, nullable=False)


class PedidoPendiente(SQLModel, table=True):
    __tablename__: ClassVar[str] = "pedidos_pendientes"

    pendiente_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    pedido_id: str = Field(default="", nullable=False, max_length=36, index=True)
    albaran_id: str = Field(default="", nullable=False, max_length=36, index=True)
    articulo_id: str = Field(default="", nullable=False, max_length=36, index=True)
    cantidad_pedida: float = Field(default=0.0, nullable=False)
    cantidad_recibida: float = Field(default=0.0, nullable=False)
    cantidad_pendiente: float = Field(default=0.0, nullable=False)
    estado: str = Field(default="pendiente", nullable=False, max_length=30, index=True)
    fecha_registro: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)


class VentaImportLote(SQLModel, table=True):
    __tablename__: ClassVar[str] = "ventas_import_lotes"

    lote_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    fuente: str = Field(default="ireks", nullable=False, max_length=20, index=True)
    cliente_id: str = Field(default="", max_length=36, index=True)
    periodo: str = Field(default="", nullable=False, max_length=7, index=True)
    archivo_nombre: str = Field(default="", max_length=255)
    archivo_hash: str = Field(default="", max_length=128, index=True)
    estado: str = Field(default="importado", nullable=False, max_length=30, index=True)
    creado_en: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)


class VentaMensualRaw(SQLModel, table=True):
    __tablename__: ClassVar[str] = "ventas_mensuales_raw"

    raw_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    lote_id: str = Field(default="", nullable=False, max_length=36, index=True)
    fuente: str = Field(default="ireks", nullable=False, max_length=20, index=True)
    cliente_id: str = Field(default="", max_length=36, index=True)
    periodo: str = Field(default="", nullable=False, max_length=7, index=True)
    articulo_codigo_origen: str = Field(default="", max_length=120, index=True)
    articulo_id: str = Field(default="", max_length=36, index=True)
    articulo_descripcion_origen: str = Field(default="", max_length=255)
    venta_kilos: float = Field(default=0.0)
    venta_kilos_sc: float = Field(default=0.0)
    venta_euros: float = Field(default=0.0)
    payload_json: str = Field(default="")


class Receta(TimeStampedModel, table=True):
    __tablename__: ClassVar[str] = "recetas"

    id: Optional[int] = Field(default=None, primary_key=True)
    cliente_id: str = Field(foreign_key="clientes.cliente_id", nullable=False, index=True, max_length=36)
    nombre: str = Field(max_length=255)
    codigo_receta: str = Field(index=True, max_length=100)
    version: str = Field(default="1.0", max_length=20)
    es_base: bool = Field(default=False)
    receta_base_id: Optional[int] = Field(default=None, foreign_key="recetas.id")
    masa_final_deseada_g: float = Field(default=0.0)
    peso_pieza_g: float = Field(default=0.0)
    numero_piezas: int = Field(default=1)
    total_harinas_g: float = Field(default=0.0)
    total_liquidos_g: float = Field(default=0.0)
    hidratacion_pct: float = Field(default=0.0)
    total_porcentaje_panadero: float = Field(default=0.0)
    masa_total_g: float = Field(default=0.0)
    coste_total: float = Field(default=0.0)
    coste_kg: float = Field(default=0.0)
    coste_pieza: float = Field(default=0.0)
    merma_pct: float = Field(default=0.0)
    observaciones: str = Field(default="")
    proceso: str = Field(default="")
    escandallo_detalle_json: str = Field(default="")
    parametros_elaboracion_json: str = Field(default="")
    estado: str = Field(default="borrador", max_length=30)


class RecetaLinea(SQLModel, table=True):
    __tablename__: ClassVar[str] = "receta_lineas"

    id: Optional[int] = Field(default=None, primary_key=True)
    receta_id: int = Field(foreign_key="recetas.id", nullable=False, index=True)
    orden: int = Field(default=0)
    tipo_origen: str = Field(default="std", max_length=20)
    ingrediente_id: Optional[int] = Field(default=None)
    nombre_mostrado: str = Field(default="", max_length=255)
    codigo_ingrediente: str = Field(default="", max_length=100)
    familia: str = Field(default="", max_length=100)
    subfamilia: str = Field(default="", max_length=100)
    es_harina: bool = Field(default=False)
    es_liquido: bool = Field(default=False)
    cantidad_base_g: float = Field(default=0.0)
    porcentaje_panadero: float = Field(default=0.0)
    cantidad_calculada_g: float = Field(default=0.0)
    precio_kg_snapshot: float = Field(default=0.0)
    coste_linea: float = Field(default=0.0)
    tipo_linea: str = Field(default="ingrediente", max_length=20, index=True)
    proceso_nombre: str = Field(default="Masa final", max_length=120, index=True)
    proceso_origen_nombre: str = Field(default="", max_length=120, index=True)
    cantidad_origen_g: float = Field(default=0.0)
    es_subreceta: bool = Field(default=False)
    subreceta_id: Optional[int] = Field(default=None, foreign_key="recetas.id")
    notas: str = Field(default="")


class RecetaVersion(SQLModel, table=True):
    __tablename__: ClassVar[str] = "receta_versiones"

    id: Optional[int] = Field(default=None, primary_key=True)
    receta_id: int = Field(foreign_key="recetas.id", nullable=False, index=True)
    version: str = Field(max_length=20)
    snapshot_json: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    comentario: str = Field(default="")


class Escandallo(SQLModel, table=True):
    __tablename__: ClassVar[str] = "escandallos"

    id: Optional[int] = Field(default=None, primary_key=True)
    receta_id: int = Field(foreign_key="recetas.id", nullable=False, index=True)
    fecha_calculo: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    masa_total_g: float = Field(default=0.0)
    coste_total: float = Field(default=0.0)
    coste_kg: float = Field(default=0.0)
    coste_pieza: float = Field(default=0.0)
    detalle_json: str = Field(default="")

