from datetime import datetime
import re

class Helper:
    
    @staticmethod
    def php_empty(x) -> bool:
        return x is None or x is False or x == '' or x == 0 or x == '0'

    @staticmethod
    def _to_php_str(x) -> str:
        return '' if Helper.php_empty(x) else str(x)

    @staticmethod
    def is_numeric_php(x) -> bool:
        if isinstance(x, (int, float)):
            return True
        s = str(x).strip()
        if s == '':
            return False
        return bool(re.fullmatch(r'[+\-]?\d+(\.\d+)?([eE][+\-]?\d+)?', s))

    @staticmethod
    def php_int(x) -> int:
        if Helper.is_numeric_php(x):
            try:
                return int(float(str(x)))
            except Exception:
                return 0
        return 0

    @staticmethod
    def only_digits(s: str) -> str:
        return re.sub(r'[^0-9]+', '', s or '')

    @staticmethod
    def only_letters(s: str) -> str:
        return re.sub(r'[^A-Za-z]+', '', s or '')

    @staticmethod
    def EmptyComodin(value, comodin) -> bool:
        value = Helper._to_php_str(value)
        comodin = Helper._to_php_str(comodin)
        return (value != "") and (comodin not in value)

    @staticmethod
    def BeginStart(desde, hasta, comodin) -> bool:
        desde = Helper._to_php_str(desde).replace(Helper._to_php_str(comodin), "")
        hasta = Helper._to_php_str(hasta)
        return (hasta != "") and desde.startswith(hasta)

    @staticmethod
    def BeginAllStart(desde, hasta, comodin) -> bool:
        desde = Helper._to_php_str(desde).replace(Helper._to_php_str(comodin), "")
        hasta = Helper._to_php_str(hasta).replace(Helper._to_php_str(comodin), "")
        return ((hasta != "" and desde.startswith(hasta)) or
                (desde != "" and hasta.startswith(desde)))

    # @staticmethod
    # def _to_str(x):
    #     return "" if x is None else str(x)

    # @staticmethod
    # def _is_numeric_int(x) -> bool:
    #     """
    #     Emula is_numeric() en el uso de este código:
    #     - En tu PHP luego casteas a (int), por eso aquí validamos enteros.
    #     - Acepta strings como '0012' o '-5'.
    #     """
    #     try:
    #         s = Helper._to_str(x).strip()
    #         if s == "":
    #             return False
    #         # Permite signo negativo opcional y dígitos
    #         if s[0] in "+-":
    #             return s[1:].isdigit()
    #         return s.isdigit()
    #     except Exception:
    #         return False

    # @staticmethod
    # def EmptyComodin(value, comodin) -> bool:
    #     """
    #     PHP: return ($value !== "" && strpos($value, $comodin) === false)
    #     """
    #     value = Helper._to_str(value)
    #     comodin = Helper._to_str(comodin)
    #     return (value != "") and (comodin not in value)

    # @staticmethod
    # def BeginStart(desde, hasta, comodin) -> bool:
    #     """
    #     PHP:
    #       $desde = str_replace($comodin, "", $desde);
    #       return ($hasta !== "" && strpos($desde, $hasta) === 0);
    #     """
    #     desde = Helper._to_str(desde).replace(Helper._to_str(comodin), "")
    #     hasta = Helper._to_str(hasta)
    #     if hasta != "" and desde.startswith(hasta):
    #         return True
    #     return False

    # @staticmethod
    # def BeginAllStart(desde, hasta, comodin) -> bool:
    #     """
    #     PHP:
    #       $desde = str_replace($comodin, "", $desde);
    #       $hasta = str_replace($comodin, "", $hasta);
    #       return (($hasta !== "" && strpos($desde, $hasta) === 0) || ($desde !== "" && strpos($hasta, $desde) === 0));
    #     """
    #     desde = Helper._to_str(desde).replace(Helper._to_str(comodin), "")
    #     hasta = Helper._to_str(hasta).replace(Helper._to_str(comodin), "")
    #     if (hasta != "" and desde.startswith(hasta)) or (desde != "" and hasta.startswith(desde)):
    #         return True
    #     return False

    @staticmethod
    def BolCampoFind(desde, hasta, desde_perfil, hasta_perfil, comodin) -> bool:
        """
        Traducción literal de la lógica condicional.
        Devuelve True/False EXACTAMENTE con las mismas condiciones que tu PHP.
        """
        BolCampo = False
        ingreso = 0

        # Normalización de vacíos como en PHP
        desde = Helper._to_php_str(desde)
        desde_perfil = Helper._to_php_str(desde_perfil)
        hasta = Helper._to_php_str(hasta)
        hasta_perfil = Helper._to_php_str(hasta_perfil)
        comodin = Helper._to_php_str(comodin)

        # 1)
        if (desde == comodin) or (desde_perfil == comodin) or (desde == desde_perfil):
            BolCampo = True
            ingreso = 1

        # 2)
        elif (Helper.is_numeric_php(desde)
              and desde_perfil == "0*"
              and hasta_perfil == "9*"
              and int(desde) >= 0):
            BolCampo = True
            ingreso = 2

        # 3) (redundante con 1, pero se mantiene)
        elif (desde == desde_perfil):
            BolCampo = True
            ingreso = 3

        # 4) Grupo numérico cuando $desde es numérico
        elif Helper.is_numeric_php(desde):
            
            d  = Helper.php_int(desde)
            dp = Helper.php_int(desde_perfil)  # SIEMPRE int
            h  = Helper.php_int(hasta) if Helper.is_numeric_php(hasta) else hasta
            hp = Helper.php_int(hasta_perfil) if Helper.is_numeric_php(hasta_perfil) else hasta_perfil


            # 4.1) ($desde === $desde_perfil) && $hasta === "" && $desde_perfil !== "" && $hasta_perfil === ""
            if (isinstance(dp, int) and d == dp) and (hasta == "") and (desde_perfil != "") and (hasta_perfil == ""):
                BolCampo = True
                ingreso = 4

            # 4.2) ($desde >= $desde_perfil && $desde <= $hasta_perfil) && $hasta === "" && $desde_perfil !== "" && $hasta_perfil !== ""
            elif (isinstance(dp, int) and isinstance(hp, int)
                  and (d >= dp and d <= hp)
                  and (hasta == "") and (desde_perfil != "") and (hasta_perfil != "")):
                BolCampo = True
                ingreso = 5

            # 4.3) ($desde_perfil >= $desde && $desde_perfil <= $hasta) && $hasta !== "" && $desde_perfil !== "" && $hasta_perfil === ""
            elif (isinstance(dp, int) and isinstance(h, int)
                  and (dp >= d and dp <= h)
                  and (hasta != "") and (desde_perfil != "") and (hasta_perfil == "")):
                BolCampo = True
                ingreso = 6

            # 4.4) ($hasta >= $hasta_perfil && $desde <= $hasta_perfil) && $hasta !== "" && $desde_perfil !== "" && $hasta_perfil !== ""
            elif (isinstance(h, int) and isinstance(hp, int)
                  and (h >= hp and d <= hp)
                  and (hasta != "") and (desde_perfil != "") and (hasta_perfil != "")):
                BolCampo = True
                ingreso = 7

        # 5)
        elif ((desde == desde_perfil)
              and Helper.EmptyComodin(desde, comodin)
              and hasta == ""
              and Helper.EmptyComodin(desde_perfil, comodin)
              and hasta_perfil == ""):
            BolCampo = True
            ingreso = 8

        # 6)
        elif ((Helper._to_php_str(desde) >= Helper._to_php_str(desde_perfil)
               and Helper._to_php_str(desde) <= Helper._to_php_str(hasta_perfil))
              and Helper.EmptyComodin(desde, comodin)
              and hasta == ""
              and Helper.EmptyComodin(desde_perfil, comodin)
              and Helper.EmptyComodin(hasta_perfil, comodin)):
            BolCampo = True
            ingreso = 9

        # 7)
        elif ((Helper._to_php_str(desde_perfil) >= Helper._to_php_str(desde)
               and Helper._to_php_str(desde_perfil) <= Helper._to_php_str(hasta))
              and Helper.EmptyComodin(desde, comodin)
              and Helper.EmptyComodin(hasta, comodin)
              and Helper.EmptyComodin(desde_perfil, comodin)
              and hasta_perfil == ""):
            BolCampo = True
            ingreso = 10

        # 8)
        elif ((Helper._to_php_str(hasta) >= Helper._to_php_str(hasta_perfil)
               and Helper._to_php_str(desde) <= Helper._to_php_str(hasta_perfil))
              and Helper.EmptyComodin(desde, comodin)
              and Helper.EmptyComodin(hasta, comodin)
              and Helper.EmptyComodin(desde_perfil, comodin)
              and Helper.EmptyComodin(hasta_perfil, comodin)):
            BolCampo = True
            ingreso = 11

        # 9)
        elif (Helper.BeginStart(desde, desde_perfil, comodin)
              and not Helper.EmptyComodin(desde, comodin)
              and hasta == ""
              and Helper.EmptyComodin(desde_perfil, comodin)
              and hasta_perfil == ""):
            BolCampo = True
            ingreso = 12

        # 10)
        elif ((Helper.BeginStart(desde, desde_perfil, comodin)
               or Helper.BeginStart(desde, hasta_perfil, comodin))
              and not Helper.EmptyComodin(desde, comodin)
              and hasta == ""
              and Helper.EmptyComodin(desde_perfil, comodin)
              and Helper.EmptyComodin(hasta_perfil, comodin)):
            BolCampo = True
            ingreso = 13

        # 11)
        elif ((Helper.BeginStart(desde, desde_perfil, comodin)
               or Helper.BeginStart(hasta, desde_perfil, comodin))
              and not Helper.EmptyComodin(desde, comodin)
              and not Helper.EmptyComodin(hasta, comodin)
              and Helper.EmptyComodin(desde_perfil, comodin)
              and hasta_perfil == ""):
            BolCampo = True
            ingreso = 14

        # 12)
        elif ((Helper.BeginStart(desde, desde_perfil, comodin)
               or Helper.BeginStart(hasta, desde_perfil, comodin)
               or Helper.BeginStart(desde, hasta_perfil, comodin)
               or Helper.BeginStart(hasta, hasta_perfil, comodin))
              and not Helper.EmptyComodin(desde, comodin)
              and not Helper.EmptyComodin(hasta, comodin)
              and Helper.EmptyComodin(desde_perfil, comodin)
              and Helper.EmptyComodin(hasta_perfil, comodin)):
            BolCampo = True
            ingreso = 15

        # 13)
        elif (Helper.BeginStart(desde_perfil, desde, comodin)
              and Helper.EmptyComodin(desde, comodin)
              and hasta == ""
              and not Helper.EmptyComodin(desde_perfil, comodin)
              and hasta_perfil == ""):
            BolCampo = True
            ingreso = 16

        # 14)
        elif ((Helper.BeginStart(desde_perfil, desde, comodin)
               or Helper.BeginStart(hasta_perfil, desde, comodin))
              and Helper.EmptyComodin(desde, comodin)
              and hasta == ""
              and not Helper.EmptyComodin(desde_perfil, comodin)
              and hasta_perfil == ""):
            BolCampo = True
            ingreso = 17

        # 15)
        elif ((Helper.BeginStart(desde_perfil, desde, comodin)
               or Helper.BeginStart(desde_perfil, hasta, comodin))
              and Helper.EmptyComodin(desde, comodin)
              and Helper.EmptyComodin(hasta, comodin)
              and not Helper.EmptyComodin(desde_perfil, comodin)
              and hasta_perfil == ""):
            BolCampo = True
            ingreso = 18

        # 16)
        elif ((Helper.BeginStart(desde_perfil, desde, comodin)
               or Helper.BeginStart(desde_perfil, hasta, comodin)
               or Helper.BeginStart(hasta_perfil, desde, comodin)
               or Helper.BeginStart(hasta_perfil, hasta, comodin))
              and Helper.EmptyComodin(desde, comodin)
              and Helper.EmptyComodin(hasta, comodin)
              and not Helper.EmptyComodin(desde_perfil, comodin)
              and not Helper.EmptyComodin(hasta_perfil, comodin)):
            BolCampo = True
            ingreso = 19

        # 17) (tres variantes)
        elif (Helper.BeginAllStart(desde, desde_perfil, comodin)
              and not Helper.EmptyComodin(desde, comodin)
              and hasta == ""
              and not Helper.EmptyComodin(desde_perfil, comodin)
              and hasta_perfil == ""):
            BolCampo = True
            ingreso = 20

        elif (Helper.BeginAllStart(desde, desde_perfil, comodin)
              and not Helper.EmptyComodin(desde, comodin)
              and hasta == ""
              and Helper.EmptyComodin(desde_perfil, comodin)
              and hasta_perfil == ""):
            BolCampo = True
            ingreso = 21

        elif (Helper.BeginAllStart(desde, desde_perfil, comodin)
              and Helper.EmptyComodin(desde, comodin)
              and hasta == ""
              and not Helper.EmptyComodin(desde_perfil, comodin)
              and hasta_perfil == ""):
            BolCampo = True
            ingreso = 22

        # 18)
        elif ((Helper.BeginAllStart(desde, desde_perfil, comodin)
               or Helper.BeginAllStart(desde, hasta_perfil, comodin))
              and not Helper.EmptyComodin(desde, comodin)
              and hasta == ""
              and not Helper.EmptyComodin(desde_perfil, comodin)
              and not Helper.EmptyComodin(hasta_perfil, comodin)):
            BolCampo = True
            ingreso = 23

        # 19)
        elif ((Helper.BeginAllStart(desde, desde_perfil, comodin)
               or Helper.BeginAllStart(hasta, desde_perfil, comodin))
              and not Helper.EmptyComodin(desde, comodin)
              and not Helper.EmptyComodin(hasta, comodin)
              and not Helper.EmptyComodin(desde_perfil, comodin)
              and hasta_perfil == ""):
            BolCampo = True
            ingreso = 24

        # 20)
        elif ((Helper.BeginAllStart(desde, desde_perfil, comodin)
               or Helper.BeginAllStart(desde, hasta_perfil, comodin)
               or Helper.BeginAllStart(hasta, desde_perfil, comodin)
               or Helper.BeginAllStart(hasta, hasta_perfil, comodin))
              and not Helper.EmptyComodin(desde, comodin)
              and not Helper.EmptyComodin(hasta, comodin)
              and not Helper.EmptyComodin(desde_perfil, comodin)
              and not Helper.EmptyComodin(hasta_perfil, comodin)):
            BolCampo = True
            ingreso = 25

        return BolCampo

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
        - Si True, push en aResultPerfiles["Actividad"][IdActividad]["TransaccionPerfiles"][Transaccion][]
        - Devuelve {'BolCampo': bool, 'aResultPerfiles': dict}
        """
        BolCampo = Helper.BolCampoFind(desde, hasta, desde_perfil, hasta_perfil, comodin)

        if BolCampo:
            aResultPerfiles.setdefault("Actividad", {})
            aResultPerfiles["Actividad"].setdefault(IdActividad, {})
            aResultPerfiles["Actividad"][IdActividad].setdefault("TransaccionPerfiles", {})
            aResultPerfiles["Actividad"][IdActividad]["TransaccionPerfiles"].setdefault(Transaccion, [])

            aResultPerfiles["Actividad"][IdActividad]["TransaccionPerfiles"][Transaccion].append({
                "IdTransaccion": Transaccion,
                "IdSapPerfil": IdPerfil,
                "IdSapAutorizacion": IdSapAutorizacion,
                "IdSapRol": IdSapRol,
                "IdObjeto": IdSapObjetoProceso,
                "Objeto": Objeto,
                "IdCampo": IdSapCampoProceso,
                "Campo": Campo,
                "Desde": Helper._to_php_str(desde_perfil),
                "Hasta": Helper._to_php_str(hasta_perfil),
            })

        return {"BolCampo": BolCampo, "aResultPerfiles": aResultPerfiles}
    
    @staticmethod
    def prepare_errors(error_list):
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_errors": len(error_list),
            "details": error_list
        }
