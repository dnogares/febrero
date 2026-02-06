#!/usr/bin/env python3
"""
Crea el archivo CSV con las 50 ciudades automáticamente
"""

from pathlib import Path

csv_content = """municipio,codigo_ine,provincia,ccaa,ambito,tipo_norma,numero_modificacion,plan_base,articulo,apartado,titulo,descripcion,url_oficial,vigente
Madrid,28079,Madrid,Comunidad de Madrid,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Madrid,PGOU vigente del municipio de Madrid,https://sede.madrid.es/portal/site/tramites,True
Barcelona,08019,Barcelona,Cataluña,municipal,PGOU,,,,,Plan General Metropolitano de Barcelona,PGM vigente de Barcelona,https://ajuntament.barcelona.cat/seuelect/,True
Valencia,46250,Valencia,Comunidad Valenciana,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Valencia,PGOU vigente de Valencia,https://www.valencia.es,True
Sevilla,41091,Sevilla,Andalucía,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Sevilla,PGOU vigente de Sevilla,https://www.sevilla.org,True
Zaragoza,50297,Zaragoza,Aragón,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Zaragoza,PGOU vigente de Zaragoza,https://www.zaragoza.es,True
Málaga,29067,Málaga,Andalucía,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Málaga,PGOU vigente de Málaga,https://sede.malaga.eu,True
Murcia,30030,Murcia,Región de Murcia,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Murcia,PGOU vigente de Murcia,https://sede.murcia.es,True
Palma,07040,Islas Baleares,Islas Baleares,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Palma,PGOU vigente de Palma,https://sede.palma.es,True
Las Palmas de Gran Canaria,35016,Las Palmas,Canarias,municipal,PGOU,,,,,Plan General de Ordenación de Las Palmas,PGOU vigente de Las Palmas de Gran Canaria,https://www.laspalmasgc.es,True
Bilbao,48020,Vizcaya,País Vasco,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Bilbao,PGOU vigente de Bilbao,https://www.bilbao.eus,True
Alicante,03014,Alicante,Comunidad Valenciana,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Alicante,PGOU vigente de Alicante,https://www.alicante.es,True
Córdoba,14021,Córdoba,Andalucía,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Córdoba,PGOU vigente de Córdoba,https://www.cordoba.es,True
Valladolid,47186,Valladolid,Castilla y León,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Valladolid,PGOU vigente de Valladolid,https://www.valladolid.es,True
Vigo,36057,Pontevedra,Galicia,municipal,PGOU,,,,,Plan General de Ordenación Municipal de Vigo,PGOU vigente de Vigo,https://sede.vigo.org,True
Gijón,33024,Asturias,Asturias,municipal,PGOU,,,,,Plan General de Ordenación de Gijón,PGOU vigente de Gijón,https://www.gijon.es,True
L'Hospitalet de Llobregat,08101,Barcelona,Cataluña,municipal,PGOU,,,,,Plan General Metropolitano de L'Hospitalet,PGM vigente de L'Hospitalet de Llobregat,https://www.l-h.cat,True
Vitoria-Gasteiz,01059,Álava,País Vasco,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Vitoria-Gasteiz,PGOU vigente de Vitoria-Gasteiz,https://www.vitoria-gasteiz.org,True
A Coruña,15030,A Coruña,Galicia,municipal,PGOU,,,,,Plan General de Ordenación Municipal de A Coruña,PGOU vigente de A Coruña,https://www.coruna.gal,True
Granada,18087,Granada,Andalucía,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Granada,PGOU vigente de Granada,https://www.granada.org,True
Elche,03065,Alicante,Comunidad Valenciana,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Elche,PGOU vigente de Elche,https://www.elche.es,True
Oviedo,33044,Asturias,Asturias,municipal,PGOU,,,,,Plan General de Ordenación de Oviedo,PGOU vigente de Oviedo,https://www.oviedo.es,True
Badalona,08015,Barcelona,Cataluña,municipal,PGOU,,,,,Plan General Metropolitano de Badalona,PGM vigente de Badalona,https://www.badalona.cat,True
Cartagena,30016,Murcia,Región de Murcia,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Cartagena,PGOU vigente de Cartagena,https://www.cartagena.es,True
Terrassa,08279,Barcelona,Cataluña,municipal,PGOU,,,,,Plan General Metropolitano de Terrassa,PGM vigente de Terrassa,https://www.terrassa.cat,True
Jerez de la Frontera,11020,Cádiz,Andalucía,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Jerez,PGOU vigente de Jerez de la Frontera,https://www.jerez.es,True
Sabadell,08187,Barcelona,Cataluña,municipal,PGOU,,,,,Plan General Metropolitano de Sabadell,PGM vigente de Sabadell,https://www.sabadell.cat,True
Santa Cruz de Tenerife,38038,Santa Cruz de Tenerife,Canarias,municipal,PGOU,,,,,Plan General de Ordenación de Santa Cruz,PGOU vigente de Santa Cruz de Tenerife,https://www.santacruzdetenerife.es,True
Móstoles,28092,Madrid,Comunidad de Madrid,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Móstoles,PGOU vigente de Móstoles,https://www.mostoles.es,True
Alcalá de Henares,28005,Madrid,Comunidad de Madrid,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Alcalá de Henares,PGOU vigente de Alcalá de Henares,https://www.ayto-alcaladehenares.es,True
Pamplona,31201,Navarra,Navarra,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Pamplona,PGOU vigente de Pamplona,https://www.pamplona.es,True
Fuenlabrada,28058,Madrid,Comunidad de Madrid,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Fuenlabrada,PGOU vigente de Fuenlabrada,https://www.ayto-fuenlabrada.es,True
Almería,04013,Almería,Andalucía,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Almería,PGOU vigente de Almería,https://www.almeria.es,True
Leganés,28074,Madrid,Comunidad de Madrid,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Leganés,PGOU vigente de Leganés,https://www.leganes.org,True
Donostia-San Sebastián,20069,Guipúzcoa,País Vasco,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Donostia,PGOU vigente de Donostia-San Sebastián,https://www.donostia.eus,True
Getafe,28065,Madrid,Comunidad de Madrid,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Getafe,PGOU vigente de Getafe,https://www.getafe.es,True
Burgos,09059,Burgos,Castilla y León,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Burgos,PGOU vigente de Burgos,https://www.aytoburgos.es,True
Albacete,02003,Albacete,Castilla-La Mancha,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Albacete,PGOU vigente de Albacete,https://www.albacete.es,True
Santander,39075,Cantabria,Cantabria,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Santander,PGOU vigente de Santander,https://santander.es,True
Castellón de la Plana,12040,Castellón,Comunidad Valenciana,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Castellón,PGOU vigente de Castellón de la Plana,https://www.castello.es,True
Alcorcón,28007,Madrid,Comunidad de Madrid,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Alcorcón,PGOU vigente de Alcorcón,https://www.ayto-alcorcon.es,True
Logroño,26089,La Rioja,La Rioja,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Logroño,PGOU vigente de Logroño,https://www.logrono.es,True
Badajoz,06015,Badajoz,Extremadura,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Badajoz,PGOU vigente de Badajoz,https://www.aytobadajoz.es,True
Salamanca,37274,Salamanca,Castilla y León,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Salamanca,PGOU vigente de Salamanca,https://www.aytosalamanca.es,True
Huelva,21041,Huelva,Andalucía,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Huelva,PGOU vigente de Huelva,https://www.huelva.es,True
Marbella,29069,Málaga,Andalucía,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Marbella,PGOU vigente de Marbella,https://www.marbella.es,True
Lleida,25120,Lleida,Cataluña,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Lleida,PGOU vigente de Lleida,https://www.paeria.cat,True
Tarragona,43148,Tarragona,Cataluña,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Tarragona,PGOU vigente de Tarragona,https://www.tarragona.cat,True
León,24089,León,Castilla y León,municipal,PGOU,,,,,Plan General de Ordenación Urbana de León,PGOU vigente de León,https://www.aytoleon.es,True
Cádiz,11012,Cádiz,Andalucía,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Cádiz,PGOU vigente de Cádiz,https://www.cadiz.es,True
Dos Hermanas,41038,Sevilla,Andalucía,municipal,PGOU,,,,,Plan General de Ordenación Urbana de Dos Hermanas,PGOU vigente de Dos Hermanas,https://www.doshermanas.es,True"""

# Guardar archivo
with open("catalogo_50_ciudades_espana.csv", "w", encoding="utf-8") as f:
    f.write(csv_content)

print("✅ Archivo CSV creado: catalogo_50_ciudades_espana.csv")
print("📍 Ubicación:", Path("catalogo_50_ciudades_espana.csv").absolute())
print("\n▶️ Ahora ejecuta: python importar_50_ciudades_corregido.py")
