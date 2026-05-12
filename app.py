import os
from datetime import datetime, timedelta, date
from flask import Flask, render_template, jsonify, request
from supabase import create_client

# Credenciais vêm SEMPRE de variáveis de ambiente (Render)
# Localmente, carrega do config.py se existir
try:
    import config as _cfg
    _SUPABASE_URL = _cfg.SUPABASE_URL
    _SUPABASE_KEY = _cfg.SUPABASE_KEY_PUBLIC
    _PORT         = _cfg.DASHBOARD_PORT
except ImportError:
    _SUPABASE_URL = ""
    _SUPABASE_KEY = ""
    _PORT         = 5000

SUPABASE_URL = os.environ.get("SUPABASE_URL", _SUPABASE_URL)
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", _SUPABASE_KEY)

app = Flask(__name__, static_folder="static")
sb  = create_client(SUPABASE_URL, SUPABASE_KEY)

DIAS_PT    = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
DIAS_ABREV = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def enriquecer(rows_raw, data_ini: date, data_fim: date):
    mapa       = {r["data_ref"]: r["quantidade"] for r in rows_raw}
    total_dias = (data_fim - data_ini).days + 1
    resultado  = []
    total      = 0

    for i in range(total_dias):
        d   = data_ini + timedelta(days=i)
        ds  = d.strftime("%Y-%m-%d")
        wd  = d.weekday()
        qtd = mapa.get(ds, 0)
        total += qtd
        resultado.append({
            "data_ref":   ds,
            "data_fmt":   d.strftime("%d/%m/%Y"),
            "dia_nome":   DIAS_PT[wd],
            "dia_abrev":  DIAS_ABREV[wd],
            "quantidade": qtd,
        })

    n      = len(resultado)
    media  = round(total / n, 1) if n else 0
    maximo = max((r["quantidade"] for r in resultado), default=0)

    for r in resultado:
        r["diff_media"] = round(r["quantidade"] - media, 1)

    return {
        "dias":        resultado,
        "total":       total,
        "media":       media,
        "maximo":      maximo,
        "periodo_ini": data_ini.strftime("%d/%m/%Y"),
        "periodo_fim": data_fim.strftime("%d/%m/%Y"),
        "erro":        None,
    }


def resolver_datas(args):
    de  = args.get("de", "")
    ate = args.get("ate", "")
    if de and ate:
        data_ini = datetime.strptime(de,  "%Y-%m-%d").date()
        data_fim = datetime.strptime(ate, "%Y-%m-%d").date()
        if data_ini > data_fim:
            data_ini, data_fim = data_fim, data_ini
    else:
        dias     = max(1, min(30, int(args.get("dias", 30))))
        data_fim = datetime.now().date()
        data_ini = data_fim - timedelta(days=dias - 1)
    return data_ini, data_fim


@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/importadas")
def api_importadas():
    try:
        data_ini, data_fim = resolver_datas(request.args)
        r = sb.table("notas_importadas") \
              .select("data_ref,quantidade") \
              .gte("data_ref", data_ini.isoformat()) \
              .lte("data_ref", data_fim.isoformat()) \
              .execute()
        return jsonify(enriquecer(r.data, data_ini, data_fim))
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/pendentes")
def api_pendentes():
    try:
        data_ini, data_fim = resolver_datas(request.args)
        r = sb.table("notas_pendentes") \
              .select("data_ref,quantidade") \
              .gte("data_ref", data_ini.isoformat()) \
              .lte("data_ref", data_fim.isoformat()) \
              .execute()
        return jsonify(enriquecer(r.data, data_ini, data_fim))
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/ultima-sync")
def api_ultima_sync():
    try:
        r = sb.table("notas_importadas") \
              .select("sincronizado_em") \
              .order("sincronizado_em", desc=True) \
              .limit(1).execute()
        ts = r.data[0]["sincronizado_em"] if r.data else None
        if ts:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            ts = dt.strftime("%d/%m/%Y %H:%M")
        return jsonify({"ultima_sync": ts or "nunca"})
    except Exception as e:
        return jsonify({"ultima_sync": "erro"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", _PORT))
    print(f"\n  Dashboard: http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
