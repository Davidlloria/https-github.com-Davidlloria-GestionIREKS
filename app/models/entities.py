from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class TimeStampedModel(SQLModel):
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class Cliente(TimeStampedModel, table=True):
    __tablename__ = "clientes"

    id: Optional[int] = Field(default=None, primary_key=True)
    codigo: str = Field(index=True, unique=True, max_length=50)
    nombre_fiscal: str = Field(max_length=255)
    nombre_comercial: str = Field(max_length=255)
    contacto: str = Field(default="", max_length=255)
    telefono: str = Field(default="", max_length=50)
    email: str = Field(default="", max_length=255)
    direccion: str = Field(default="")
    notas: str = Field(default="")
    activo: bool = Field(default=True)


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


class IngredienteIreks(IngredienteBase, table=True):
    __tablename__ = "ingredientes_ireks"

    id: Optional[int] = Field(default=None, primary_key=True)
    referencia: str = Field(default="", max_length=100)


class IngredienteStd(IngredienteBase, table=True):
    __tablename__ = "ingredientes_std"

    id: Optional[int] = Field(default=None, primary_key=True)


class Receta(TimeStampedModel, table=True):
    __tablename__ = "recetas"

    id: Optional[int] = Field(default=None, primary_key=True)
    cliente_id: int = Field(foreign_key="clientes.id", nullable=False, index=True)
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
    estado: str = Field(default="borrador", max_length=30)


class RecetaLinea(SQLModel, table=True):
    __tablename__ = "receta_lineas"

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
    es_subreceta: bool = Field(default=False)
    subreceta_id: Optional[int] = Field(default=None, foreign_key="recetas.id")
    notas: str = Field(default="")


class RecetaVersion(SQLModel, table=True):
    __tablename__ = "receta_versiones"

    id: Optional[int] = Field(default=None, primary_key=True)
    receta_id: int = Field(foreign_key="recetas.id", nullable=False, index=True)
    version: str = Field(max_length=20)
    snapshot_json: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    comentario: str = Field(default="")


class Escandallo(SQLModel, table=True):
    __tablename__ = "escandallos"

    id: Optional[int] = Field(default=None, primary_key=True)
    receta_id: int = Field(foreign_key="recetas.id", nullable=False, index=True)
    fecha_calculo: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    masa_total_g: float = Field(default=0.0)
    coste_total: float = Field(default=0.0)
    coste_kg: float = Field(default=0.0)
    coste_pieza: float = Field(default=0.0)
    detalle_json: str = Field(default="")
