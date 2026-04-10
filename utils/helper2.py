from datetime import datetime
import re


class Helper2:
    # --- Patrones precompilados (mismos patrones literales que tu código actual) ---
    _RE_NUMERIC = re.compile(r'\[+\\-\]?\\d+(\.\\d+)?(\[eE\]\[+\\-\]?\\d+)?')
    _RE_ONLY_DIGITS = re.compile(r'[^0-9]+')
    _RE_ONLY_LETTERS = re.compile(r'[^A-Za-z]+')

    @staticmethod
    def php_empty(x) -> bool:
        # Igual semántica que la actual
        return x is None or x is False or x == '' or x == 0 or x == '0'

    @staticmethod
    def _to_php_str(x) -> str:
        # Igual semántica que la actual
        return '' if Helper2.php_empty(x) else str(x)

    @staticmethod
    def is_numeric_php(x) -> bool:
        # Mantiene el patrón literal original (aunque esté "sobre-escapeado")
        if isinstance(x, (int, float)):
            return True
        s = str(x).strip()
        if s == '':
            return False
        return bool(Helper2._RE_NUMERIC.fullmatch(s))

    @staticmethod
    def php_int(x) -> int:
        # Respeta la secuencia actual: primero is_numeric_php, luego cast vía float->int
        if Helper2.is_numeric_php(x):
            try:
                return int(float(str(x)))
            except Exception:
                return 0
        return 0

    @staticmethod
    def only_digits(s: str) -> str:
        return Helper2._RE_ONLY_DIGITS.sub('', s or '')

    @staticmethod
    def only_letters(s: str) -> str:
        return Helper2._RE_ONLY_LETTERS.sub('', s or '')

    @staticmethod
    def EmptyComodin(value, comodin) -> bool:
        value = Helper2._to_php_str(value)
        comodin = Helper2._to_php_str(comodin)
        return (value != "") and (comodin not in value)

    @staticmethod
    def BeginStart(desde, hasta, comodin) -> bool:
        desde = Helper2._to_php_str(desde).replace(Helper2._to_php_str(comodin), "")
        hasta = Helper2._to_php_str(hasta)
        return (hasta != "") and desde.startswith(hasta)

    @staticmethod
    def BeginAllStart(desde, hasta, comodin) -> bool:
        desde = Helper2._to_php_str(desde).replace(Helper2._to_php_str(comodin), "")
        hasta = Helper2._to_php_str(hasta).replace(Helper2._to_php_str(comodin), "")
        return ((hasta != "" and desde.startswith(hasta)) or
                (desde != "" and hasta.startswith(desde)))

    @staticmethod
    def BolCampoFind(desde, hasta, desde_perfil, hasta_perfil, comodin) -> bool:
        """
        Traducción literal de la lógica condicional.
        Devuelve True/False EXACTAMENTE con las mismas condiciones que tu versión actual.
        """
        # --- Normalización única (idéntica a tu versión actual) ---
        s_desde = Helper2._to_php_str(desde)
        s_dp = Helper2._to_php_str(desde_perfil)
        s_hasta = Helper2._to_php_str(hasta)
        s_hp = Helper2._to_php_str(hasta_perfil)
        s_como = Helper2._to_php_str(comodin)

        # Helpers locales equivalentes (evitamos llamadas repetidas y _to_php_str internos)
        def empty_como(val: str) -> bool:
            return (val != "") and (s_como not in val)

        # Pre-remplazos para begins
        rep_desde = s_desde.replace(s_como, "") if s_como else s_desde
        rep_hasta = s_hasta.replace(s_como, "") if s_como else s_hasta
        rep_dp = s_dp.replace(s_como, "") if s_como else s_dp
        rep_hp = s_hp.replace(s_como, "") if s_como else s_hp

        def begin_start(d: str, h: str) -> bool:
            # Igual que BeginStart tras normalización previa
            return (h != "") and d.startswith(h)

        def begin_all_start(d: str, h: str) -> bool:
            # Igual que BeginAllStart tras normalización previa
            return ((h != "" and d.startswith(h)) or (d != "" and h.startswith(d)))

        # --- Condiciones (mismo orden y comparaciones) ---

        # 1)
        if (s_desde == s_como) or (s_dp == s_como) or (s_desde == s_dp):
            return True

        # 2)
        if (Helper2.is_numeric_php(s_desde)
                and s_dp == "0*"
                and s_hp == "9*"
                and int(s_desde) >= 0):
            return True

        # 3) redundante con 1, se mantiene
        if (s_desde == s_dp):
            return True

        # 4) rama numérica cuando s_desde es numérico
        if Helper2.is_numeric_php(s_desde):
            d = Helper2.php_int(s_desde)
            dp = Helper2.php_int(s_dp)  # siempre int
            h = Helper2.php_int(s_hasta) if Helper2.is_numeric_php(s_hasta) else s_hasta
            hp = Helper2.php_int(s_hp) if Helper2.is_numeric_php(s_hp) else s_hp

            # 4.1)
            if (isinstance(dp, int) and d == dp) and (s_hasta == "") and (s_dp != "") and (s_hp == ""):
                return True

            # 4.2)
            if (isinstance(dp, int) and isinstance(hp, int)
                    and (d >= dp and d <= hp)
                    and (s_hasta == "") and (s_dp != "") and (s_hp != "")):
                return True

            # 4.3)
            if (isinstance(dp, int) and isinstance(h, int)
                    and (dp >= d and dp <= h)
                    and (s_hasta != "") and (s_dp != "") and (s_hp == "")):
                return True

            # 4.4)
            if (isinstance(h, int) and isinstance(hp, int)
                    and (h >= hp and d <= hp)
                    and (s_hasta != "") and (s_dp != "") and (s_hp != "")):
                return True

        # 5)
        if ((s_desde == s_dp)
                and empty_como(s_desde)
                and s_hasta == ""
                and empty_como(s_dp)
                and s_hp == ""):
            return True

        # 6)
        if ((s_desde >= s_dp and s_desde <= s_hp)
                and empty_como(s_desde)
                and s_hasta == ""
                and empty_como(s_dp)
                and empty_como(s_hp)):
            return True

        # 7)
        if ((s_dp >= s_desde and s_dp <= s_hasta)
                and empty_como(s_desde)
                and empty_como(s_hasta)
                and empty_como(s_dp)
                and s_hp == ""):
            return True

        # 8)
        if ((s_hasta >= s_hp and s_desde <= s_hp)
                and empty_como(s_desde)
                and empty_como(s_hasta)
                and empty_como(s_dp)
                and empty_como(s_hp)):
            return True

        # 9)
        if (begin_start(rep_desde, s_dp)
                and not empty_como(s_desde)
                and s_hasta == ""
                and empty_como(s_dp)
                and s_hp == ""):
            return True

        # 10)
        if ((begin_start(rep_desde, s_dp) or begin_start(rep_desde, s_hp))
                and not empty_como(s_desde)
                and s_hasta == ""
                and empty_como(s_dp)
                and empty_como(s_hp)):
            return True

        # 11)
        if ((begin_start(rep_desde, s_dp) or begin_start(rep_hasta, s_dp))
                and not empty_como(s_desde)
                and not empty_como(s_hasta)
                and empty_como(s_dp)
                and s_hp == ""):
            return True

        # 12)
        if ((begin_start(rep_desde, s_dp)
             or begin_start(rep_hasta, s_dp)
             or begin_start(rep_desde, s_hp)
             or begin_start(rep_hasta, s_hp))
                and not empty_como(s_desde)
                and not empty_como(s_hasta)
                and empty_como(s_dp)
                and empty_como(s_hp)):
            return True

        # 13)
        if (begin_start(rep_dp, s_desde)
                and empty_como(s_desde)
                and s_hasta == ""
                and not empty_como(s_dp)
                and s_hp == ""):
            return True

        # 14)
        if ((begin_start(rep_dp, s_desde) or begin_start(rep_hp, s_desde))
                and empty_como(s_desde)
                and s_hasta == ""
                and not empty_como(s_dp)
                and s_hp == ""):
            return True

        # 15)
        if ((begin_start(rep_dp, s_desde) or begin_start(rep_dp, s_hasta))
                and empty_como(s_desde)
                and empty_como(s_hasta)
                and not empty_como(s_dp)
                and s_hp == ""):
            return True

        # 16)
        if ((begin_start(rep_dp, s_desde)
             or begin_start(rep_dp, s_hasta)
             or begin_start(rep_hp, s_desde)
             or begin_start(rep_hp, s_hasta))
                and empty_como(s_desde)
                and empty_como(s_hasta)
                and not empty_como(s_dp)
                and not empty_como(s_hp)):
            return True

        # 17) (tres variantes)
        if (begin_all_start(rep_desde, rep_dp)
                and not empty_como(s_desde)
                and s_hasta == ""
                and not empty_como(s_dp)
                and s_hp == ""):
            return True

        if (begin_all_start(rep_desde, rep_dp)
                and not empty_como(s_desde)
                and s_hasta == ""
                and empty_como(s_dp)
                and s_hp == ""):
            return True

        if (begin_all_start(rep_desde, rep_dp)
                and empty_como(s_desde)
                and s_hasta == ""
                and not empty_como(s_dp)
                and s_hp == ""):
            return True

        # 18)
        if ((begin_all_start(rep_desde, rep_dp) or begin_all_start(rep_desde, rep_hp))
                and not empty_como(s_desde)
                and s_hasta == ""
                and not empty_como(s_dp)
                and not empty_como(s_hp)):
            return True

        # 19)
        if ((begin_all_start(rep_desde, rep_dp) or begin_all_start(rep_hasta, rep_dp))
                and not empty_como(s_desde)
                and not empty_como(s_hasta)
                and not empty_como(s_dp)
                and s_hp == ""):
            return True

        # 20)
        if ((begin_all_start(rep_desde, rep_dp)
             or begin_all_start(rep_desde, rep_hp)
             or begin_all_start(rep_hasta, rep_dp)
             or begin_all_start(rep_hasta, rep_hp))
                and not empty_como(s_desde)
                and not empty_como(s_hasta)
                and not empty_como(s_dp)
                and not empty_como(s_hp)):
            return True

        return False

    @staticmethod
    def BolCampoFindObjectAuthorization(
        BolCampo,
        desde, desde_perfil, hasta, hasta_perfil, comodin,
        aResultPerfiles,
        IdActividad, Transaccion, IdPerfil, IdSapAutorizacion, IdSapRol,
        IdSapObjetoProceso, Objeto, IdSapCampoProceso, Campo
    ):
        """
        Replica exacta:
        - Evalúa BolCampoFind(...)
        - Si True, inserta en aResultPerfiles["Actividad"][IdActividad]["TransaccionPerfiles"][Transaccion][]
        - Devuelve {'BolCampo': bool, 'aResultPerfiles': dict}
        """
        BolCampo = Helper2.BolCampoFind(desde, hasta, desde_perfil, hasta_perfil, comodin)
        if BolCampo:
            actividad = aResultPerfiles.setdefault("Actividad", {})
            act = actividad.setdefault(IdActividad, {})
            trans = act.setdefault("TransaccionPerfiles", {})
            bucket = trans.setdefault(Transaccion, [])
            bucket.append({
                "IdTransaccion": Transaccion,
                "IdSapPerfil": IdPerfil,
                "IdSapAutorizacion": IdSapAutorizacion,
                "IdSapRol": IdSapRol,
                "IdObjeto": IdSapObjetoProceso,
                "Objeto": Objeto,
                "IdCampo": IdSapCampoProceso,
                "Campo": Campo,
                "Desde": Helper2._to_php_str(desde_perfil),
                "Hasta": Helper2._to_php_str(hasta_perfil),
            })

        return {"BolCampo": BolCampo, "aResultPerfiles": aResultPerfiles}

    @staticmethod
    def prepare_errors(error_list):
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_errors": len(error_list),
            "details": error_list
        }