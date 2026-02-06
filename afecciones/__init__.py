#!/usr/bin/env python3
"""
afecciones/__init__.py
Módulo de análisis de afecciones vectoriales y generación de PDFs
"""
def get_vector_analyzer():
    from .vector_analyzer import VectorAnalyzer
    return VectorAnalyzer

__all__ = ['VectorAnalyzer', 'AfeccionesPDF']