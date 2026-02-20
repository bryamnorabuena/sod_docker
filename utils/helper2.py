from datetime import datetime
import re

class Helper:
    @staticmethod
    def bol_campo_find(desde, hasta, desde_perfil, hasta_perfil, comodin):
        bol_campo = False
        ingreso = 0
        
        # Normalización más parecida a empty() de PHP
        if Helper.php_empty(desde):
            desde = ""
        if Helper.php_empty(desde_perfil):
            desde_perfil = ""
        if Helper.php_empty(hasta):
            hasta = ""
        if Helper.php_empty(hasta_perfil):
            hasta_perfil = ""

        # Condición 1 (comodines o igualdad exacta)
        if desde == comodin or desde_perfil == comodin or desde == desde_perfil:
            bol_campo = True
            ingreso = 1
        
        # Condición 2 (rango especial 0*-9*)
        elif (desde_perfil == "0*" and hasta_perfil == "9*"):
            bol_campo = True
            ingreso = 2
        
        # Condición 3 (igualdad exacta)
        elif desde == desde_perfil:
            bol_campo = True
            ingreso = 3
        
        elif Helper.is_numeric(desde):  # Grupo 1 - Números
            try:
                desde = int(desde)
                desde_perfil = int(desde_perfil) if Helper.is_numeric(desde_perfil) else desde_perfil
                hasta = int(hasta) if Helper.is_numeric(hasta) else hasta
                hasta_perfil = int(hasta_perfil) if Helper.is_numeric(hasta_perfil) else hasta_perfil

                # Caso 4 (valor exacto)
                if (Helper.is_numeric(desde_perfil) and
                    desde == desde_perfil and
                    hasta == "" and
                    desde_perfil != "" and
                    hasta_perfil == ""):
                    bol_campo = True
                    ingreso = 4

                # Caso 5 (dentro de rango)
                elif (Helper.is_numeric(desde_perfil) and
                    Helper.is_numeric(hasta_perfil) and
                    hasta == "" and
                    desde_perfil != "" and
                    hasta_perfil != "" and
                    desde >= desde_perfil and desde <= hasta_perfil):
                    bol_campo = True
                    ingreso = 5

                # Caso 6 (rango inverso)
                elif (Helper.is_numeric(desde_perfil) and
                    hasta != "" and
                    Helper.is_numeric(hasta) and
                    desde_perfil != "" and
                    hasta_perfil == "" and
                    desde_perfil >= desde and desde_perfil <= hasta):
                    bol_campo = True
                    ingreso = 6

                # Caso 7 (superposición de rangos)
                elif (Helper.is_numeric(desde_perfil) and
                    Helper.is_numeric(hasta_perfil) and
                    hasta != "" and
                    Helper.is_numeric(hasta) and
                    desde_perfil != "" and
                    hasta_perfil != "" and
                    hasta >= hasta_perfil and
                    desde <= hasta_perfil):
                    bol_campo = True
                    ingreso = 7
                    
            except Exception as e:
                print(f"Error en conversión numérica: {e}")
                pass
        elif (desde == desde_perfil 
            and Helper.empty_comodin(desde, comodin) 
            and (hasta == "" or hasta is None) 
            and Helper.empty_comodin(desde_perfil, comodin) 
            and (hasta_perfil == "" or hasta_perfil is None)):
            bol_campo = True
            ingreso = 8

        elif (desde >= desde_perfil and desde <= hasta_perfil 
            and Helper.empty_comodin(desde, comodin) 
            and (hasta == "" or hasta is None) 
            and Helper.empty_comodin(desde_perfil, comodin) 
            and Helper.empty_comodin(hasta_perfil, comodin)):
            bol_campo = True
            ingreso = 9

        elif (desde_perfil >= desde and desde_perfil <= hasta 
            and Helper.empty_comodin(desde, comodin) 
            and Helper.empty_comodin(hasta, comodin) 
            and Helper.empty_comodin(desde_perfil, comodin) 
            and (hasta_perfil == "" or hasta_perfil is None)):
            bol_campo = True
            ingreso = 10

        elif (hasta >= hasta_perfil and desde <= hasta_perfil 
            and Helper.empty_comodin(desde, comodin) 
            and Helper.empty_comodin(hasta, comodin) 
            and Helper.empty_comodin(desde_perfil, comodin) 
            and Helper.empty_comodin(hasta_perfil, comodin)):
            bol_campo = True
            ingreso = 11

        elif (Helper.begin_start(desde, desde_perfil, comodin) 
            and not Helper.empty_comodin(desde, comodin) 
            and (hasta == "" or hasta is None) 
            and Helper.empty_comodin(desde_perfil, comodin) 
            and (hasta_perfil == "" or hasta_perfil is None)):
            bol_campo = True
            ingreso = 12

        elif ((Helper.begin_start(desde, desde_perfil, comodin) 
            or Helper.begin_start(desde, hasta_perfil, comodin)) 
            and not Helper.empty_comodin(desde, comodin) 
            and (hasta == "" or hasta is None) 
            and Helper.empty_comodin(desde_perfil, comodin) 
            and Helper.empty_comodin(hasta_perfil, comodin)):
            bol_campo = True
            ingreso = 13

        elif ((Helper.begin_start(desde, desde_perfil, comodin) 
            or Helper.begin_start(hasta, desde_perfil, comodin)) 
            and not Helper.empty_comodin(desde, comodin) 
            and not Helper.empty_comodin(hasta, comodin) 
            and Helper.empty_comodin(desde_perfil, comodin) 
            and (hasta_perfil == "" or hasta_perfil is None)):
            bol_campo = True
            ingreso = 14

        elif ((Helper.begin_start(desde, desde_perfil, comodin) 
            or Helper.begin_start(hasta, desde_perfil, comodin) 
            or Helper.begin_start(desde, hasta_perfil, comodin) 
            or Helper.begin_start(hasta, hasta_perfil, comodin)) 
            and not Helper.empty_comodin(desde, comodin) 
            and not Helper.empty_comodin(hasta, comodin) 
            and Helper.empty_comodin(desde_perfil, comodin) 
            and Helper.empty_comodin(hasta_perfil, comodin)):
            bol_campo = True
            ingreso = 15

        elif (Helper.begin_start(desde_perfil, desde, comodin) 
            and Helper.empty_comodin(desde, comodin) 
            and (hasta == "" or hasta is None) 
            and not Helper.empty_comodin(desde_perfil, comodin) 
            and (hasta_perfil == "" or hasta_perfil is None)):
            bol_campo = True
            ingreso = 16

        elif ((Helper.begin_start(desde_perfil, desde, comodin) 
            or Helper.begin_start(hasta_perfil, desde, comodin)) 
            and Helper.empty_comodin(desde, comodin) 
            and (hasta == "" or hasta is None) 
            and not Helper.empty_comodin(desde_perfil, comodin) 
            and (hasta_perfil == "" or hasta_perfil is None)):
            bol_campo = True
            ingreso = 17

        elif ((Helper.begin_start(desde_perfil, desde, comodin) 
            or Helper.begin_start(desde_perfil, hasta, comodin)) 
            and Helper.empty_comodin(desde, comodin) 
            and Helper.empty_comodin(hasta, comodin) 
            and not Helper.empty_comodin(desde_perfil, comodin) 
            and (hasta_perfil == "" or hasta_perfil is None)):
            bol_campo = True
            ingreso = 18

        elif ((Helper.begin_start(desde_perfil, desde, comodin) 
            or Helper.begin_start(desde_perfil, hasta, comodin) 
            or Helper.begin_start(hasta_perfil, desde, comodin) 
            or Helper.begin_start(hasta_perfil, hasta, comodin)) 
            and Helper.empty_comodin(desde, comodin) 
            and Helper.empty_comodin(hasta, comodin) 
            and not Helper.empty_comodin(desde_perfil, comodin) 
            and not Helper.empty_comodin(hasta_perfil, comodin)):
            bol_campo = True
            ingreso = 19

        elif (Helper.begin_all_start(desde, desde_perfil, comodin) 
            and not Helper.empty_comodin(desde, comodin) 
            and (hasta == "" or hasta is None) 
            and not Helper.empty_comodin(desde_perfil, comodin) 
            and (hasta_perfil == "" or hasta_perfil is None)):
            bol_campo = True
            ingreso = 20

        elif (Helper.begin_all_start(desde, desde_perfil, comodin) 
            and not Helper.empty_comodin(desde, comodin) 
            and (hasta == "" or hasta is None) 
            and Helper.empty_comodin(desde_perfil, comodin) 
            and (hasta_perfil == "" or hasta_perfil is None)):
            bol_campo = True
            ingreso = 21

        elif (Helper.begin_all_start(desde, desde_perfil, comodin) 
            and Helper.empty_comodin(desde, comodin) 
            and (hasta == "" or hasta is None) 
            and not Helper.empty_comodin(desde_perfil, comodin) 
            and (hasta_perfil == "" or hasta_perfil is None)):
            bol_campo = True
            ingreso = 22

        elif ((Helper.begin_all_start(desde, desde_perfil, comodin) 
            or Helper.begin_all_start(desde, hasta_perfil, comodin)) 
            and not Helper.empty_comodin(desde, comodin) 
            and (hasta == "" or hasta is None) 
            and not Helper.empty_comodin(desde_perfil, comodin) 
            and not Helper.empty_comodin(hasta_perfil, comodin)):
            bol_campo = True
            ingreso = 23

        elif ((Helper.begin_all_start(desde, desde_perfil, comodin) 
            or Helper.begin_all_start(hasta, desde_perfil, comodin)) 
            and not Helper.empty_comodin(desde, comodin) 
            and not Helper.empty_comodin(hasta, comodin) 
            and not Helper.empty_comodin(desde_perfil, comodin) 
            and (hasta_perfil == "" or hasta_perfil is None)):
            bol_campo = True
            ingreso = 24

        elif ((Helper.begin_all_start(desde, desde_perfil, comodin) 
            or Helper.begin_all_start(desde, hasta_perfil, comodin) 
            or Helper.begin_all_start(hasta, desde_perfil, comodin) 
            or Helper.begin_all_start(hasta, hasta_perfil, comodin)) 
            and not Helper.empty_comodin(desde, comodin) 
            and not Helper.empty_comodin(hasta, comodin) 
            and not Helper.empty_comodin(desde_perfil, comodin) 
            and not Helper.empty_comodin(hasta_perfil, comodin)):
            bol_campo = True
            ingreso = 25

        return bol_campo

    @staticmethod
    def begin_all_start(desde, hasta, comodin):
        # str_replace($comodin, "", $desde/$hasta)
        str_desde = str(desde).replace(comodin, "") if desde is not None else ""
        str_hasta = str(hasta).replace(comodin, "") if hasta is not None else ""

        # strpos === 0 en PHP <=> .startswith en Python
        return ((str_hasta != "" and str_desde.startswith(str_hasta)) or
                (str_desde != "" and str_hasta.startswith(str_desde)))

    @staticmethod
    def begin_start(desde, hasta, comodin):
        # str_replace($comodin, "", $desde)
        str_desde = str(desde).replace(comodin, "") if desde is not None else ""
        str_hasta = str(hasta) if hasta is not None else ""

        # strpos === 0 en PHP
        return (str_hasta != "" and str_desde.startswith(str_hasta))

    @staticmethod
    def empty_comodin(value, comodin):
        str_value = str(value) if value is not None else ""

        # En PHP: ($value !== "" && strpos($value, $comodin) === false)
        return (str_value != "" and comodin not in str_value)


    @staticmethod
    def bol_campo_find_object_authorization(
        bol_campo, desde, desde_perfil, hasta, hasta_perfil, comodin,
        a_result_perfiles, id_actividad, transaccion, id_perfil,
        id_sap_autorizacion, id_sap_rol, id_sap_objeto_proceso,
        objeto, id_sap_campo_proceso, campo
    ):
        bol_campo = Helper.bol_campo_find(desde, hasta, desde_perfil, hasta_perfil, comodin)

        if bol_campo:
            # PHP hace: $aResultPerfiles["Actividad"][$IdActividad]["TransaccionPerfiles"][$Transaccion][] = array(...)
            if "ACTIVITY" not in a_result_perfiles:
                a_result_perfiles["ACTIVITY"] = {}
            if id_actividad not in a_result_perfiles["ACTIVITY"]:
                a_result_perfiles["ACTIVITY"][id_actividad] = {"TRANSACTIONPROFILES": {}}
            if transaccion not in a_result_perfiles["ACTIVITY"][id_actividad]["TRANSACTIONPROFILES"]:
                a_result_perfiles["ACTIVITY"][id_actividad]["TRANSACTIONPROFILES"][transaccion] = []

            a_result_perfiles["ACTIVITY"][id_actividad]["TRANSACTIONPROFILES"][transaccion].append({
                "IdTransaccion": transaccion,
                "IdSapPerfil": id_perfil,
                "IdSapAutorizacion": id_sap_autorizacion,
                "IdSapRol": id_sap_rol,
                "IdObjeto": id_sap_objeto_proceso,
                "Objeto": objeto,
                "IdCampo": id_sap_campo_proceso,
                "Campo": campo,
                "Desde": desde_perfil,
                "Hasta": hasta_perfil
            })

        return {"BolCampo": bol_campo, "aResultPerfiles": a_result_perfiles}
    

    @staticmethod
    def add_actividad_rol_campo(result_profiles, sap_org_levels, campo, campo_key):
        """
        Agrega información de niveles organizacionales a los resultados de perfiles
        
        Args:
            result_profiles (dict): Diccionario con los resultados de perfiles
            sap_org_levels (list): Lista de niveles organizacionales SAP
            campo (str): Nombre del campo a evaluar
            campo_key (str): Clave para almacenar en el diccionario de resultados
        
        Returns:
            dict: result_profiles actualizado
        """
        for actividad_id, item in result_profiles["Activity"].items():
            roles = item["Roles"]
            for role_id in roles:
                # Filtrar niveles organizacionales por rol y campo
                filtered_levels = [
                    level for level in sap_org_levels 
                    if level["role_id"] == role_id and level["organizational_level"] == campo
                ]
                
                if filtered_levels:
                    if role_id not in result_profiles["Activity"][actividad_id][campo_key]:
                        data = {
                            'from': filtered_levels[0]['from'],
                            'to': filtered_levels[0]['to']
                        }
                        result_profiles["Activity"][actividad_id][campo_key][role_id] = data
                        
        return result_profiles

    @staticmethod
    def bol_actividad_rol_campo(result_profiles, campo, wildcard):
        """
        Verifica condiciones booleanas sobre los campos de actividad y roles
        
        Args:
            result_profiles (dict): Diccionario con los resultados de perfiles
            campo (str): Nombre del campo a evaluar
            wildcard (str): Comodín para comparaciones
        
        Returns:
            bool: Resultado de la evaluación condicional
        """
        actividades = {}
        all_true = False
        
        for actividad_id, item in result_profiles["Activity"].items():
            campos = item[campo]
            
            # Filtrar roles que cumplan condiciones especiales
            filtered_roles = [
                role for role in campos.values() 
                if (role['from'] == wildcard or 
                    (role['from'] == '0*' and role['to'] == '9*') or
                    (role['from'] == '0' and role['to'] == 'ZZZZ'))
            ]
            
            if filtered_roles:
                all_true = True
                break
                
            if not all_true:
                # Crear copia sin la actividad actual
                copy_results = result_profiles["Activity"].copy()
                del copy_results[actividad_id]
                
                for campo_val, values in campos.items():
                    for actividad_copy_id, item_copy in copy_results.items():
                        roles_copy = item_copy[campo]
                        
                        # Filtrar roles que cumplan la condición de coincidencia
                        filtered_copy_roles = [
                            role for role in roles_copy.values()
                            if Helper.bol_campo_find(
                                role['from'], role['to'], 
                                values['from'], values['to'], 
                                wildcard
                            )
                        ]
                        
                        if filtered_copy_roles:
                            if actividad_id not in actividades:
                                actividades[actividad_id] = 0
                            actividades[actividad_id] += 1
                                
        # Evaluación final
        bol_actividad = all_true
        
        if actividades:
            total_actividades = len(result_profiles["Activity"])
            filtered_actividades = [
                count for count in actividades.values() 
                if count >= (total_actividades - 1)
            ]
            
            if filtered_actividades:
                bol_actividad = True
                
        return bol_actividad

    @staticmethod
    def prepare_errors(error_list):
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_errors": len(error_list),
            "details": error_list
        }

    @staticmethod
    def php_int_cast(value):
        # Caso 1: Valor es None o falso en PHP (null, false)
        if value is None:
            return 0
        if isinstance(value, bool):
            return 1 if value else 0
        
        # Caso 2: Ya es un número entero
        if isinstance(value, int):
            return value
        
        # Caso 3: Es un float (truncar como PHP)
        if isinstance(value, float):
            return int(value)
        
        # Caso 4: Es un string
        if isinstance(value, str):
            value = value.strip()
            if not value:  # String vacío
                return 0
            
            # Manejar notación científica que PHP interpreta
            if 'e' in value.lower():
                parts = value.lower().split('e')
                try:
                    base = float(parts[0])
                    exp = int(parts[1])
                    return int(base * (10 ** exp))
                except:
                    return 0
            
            # Extraer parte numérica inicial (como PHP)
            match = re.match(r'^([+-]?\d+)', value)
            if match:
                try:
                    return int(match.group(1))
                except:
                    return 0
            return 0
        
        # Caso 5: Otros tipos (array, objeto, etc.)
        try:
            return int(value)
        except:
            return 0


    def php_empty(value):
        return value is None or value == '' or value == 0 or value == '0' or value is False

    @staticmethod
    def is_numeric(value):
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, str) and value.strip() != "":
            try:
                float(value)  # acepta "10", "10.5", "1e3"
                return True
            except ValueError:
                return False
        return False