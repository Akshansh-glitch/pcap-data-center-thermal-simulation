"""Thermal Twin · an interactive, simulation-based engineering prototype."""
from __future__ import annotations
import copy
import json
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from python.analytics import summarize, timeline_metrics
from python.benchmark_service import benchmark, load_history, save_results
from python.engine_bridge import engine_path, environment_info
from python.model import PATTERNS, baseline_config, default_config, fields, validate_config
from python.scenario_service import list_scenarios, load_scenario, save_scenario
from python.simulation_service import Simulation
from python.visualization import benchmark_chart, heatmap, timeline

st.set_page_config(page_title="Thermal Twin", page_icon="🌡", layout="wide")
st.markdown("""<style>
 .block-container {padding-top:1.4rem; max-width:1600px}
 h1,h2,h3 {letter-spacing:-.025em; color:#172c41}
 [data-testid="stMetricValue"] {font-variant-numeric:tabular-nums}
 /* The app uses Streamlit's dark theme. Keep sidebar surfaces and text in
    that same color system; a light sidebar left white theme text unreadable. */
 section[data-testid="stSidebar"] {
   background:#17212c;
   color:#e7eef4;
   border-right:1px solid #30404e;
   min-width:260px;
   max-width:min(320px, 82vw);
 }
 section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
   background:#17212c;
 }
 section[data-testid="stSidebar"] h1,
 section[data-testid="stSidebar"] h2 {
   color:#f7fafc;
 }
 section[data-testid="stSidebar"] .eyebrow {
   color:#75d7e9;
 }
 section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
   color:#b8c8d5;
 }
 section[data-testid="stSidebar"] [data-testid="stElementContainer"]:has(> [data-testid="stRadio"]),
 section[data-testid="stSidebar"] [data-testid="stRadio"],
 section[data-testid="stSidebar"] [data-testid="stRadioGroup"] {
   width:100%;
 }
 section[data-testid="stSidebar"] [data-testid="stRadioGroup"] {
   gap:6px;
 }
 section[data-testid="stSidebar"] [data-testid="stRadioOption"] {
   box-sizing:border-box;
   display:flex;
   align-items:center;
   min-height:44px;
   width:100%;
   padding:10px 12px;
   border-radius:7px;
   background:transparent;
   color:#dce7ee;
   cursor:pointer;
   transition:background-color .15s ease, color .15s ease;
 }
 section[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div > div:first-child {
   display:none;
 }
 section[data-testid="stSidebar"] [data-testid="stRadioOption"]::before {
   content:"";
   flex:none;
   width:7px;
   height:7px;
   margin-right:13px;
   border:1px solid #94acbc;
   border-radius:50%;
 }
 section[data-testid="stSidebar"] [data-testid="stRadioOption"] [data-testid="stMarkdownContainer"] p {
   margin:0;
   color:inherit;
   font-size:.94rem;
   font-weight:500;
   white-space:normal;
 }
 section[data-testid="stSidebar"] [data-testid="stRadioOption"]:hover {
   background:#263746;
   color:#fff;
 }
 section[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] {
   background:#24404e;
   color:#fff;
   box-shadow:inset 3px 0 0 #55c8df;
 }
 section[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"]::before {
   background:#55c8df;
   border-color:#55c8df;
 }
 section[data-testid="stSidebar"] [data-testid="stRadioOption"]:focus-within {
   outline:2px solid #8ae4f5;
   outline-offset:2px;
 }
 .eyebrow {font-size:.74rem;font-weight:700;letter-spacing:.12em;color:#217e9e;text-transform:uppercase}
 .caption {color:#617381;font-size:.88rem}
 </style>""", unsafe_allow_html=True)

if "config" not in st.session_state:
    st.session_state.config = default_config()
if "simulation" not in st.session_state:
    st.session_state.simulation = Simulation(st.session_state.config)
if "running" not in st.session_state:
    st.session_state.running = False

c = st.session_state.config
sim: Simulation = st.session_state.simulation

with st.sidebar:
    st.markdown('<div class="eyebrow">PCAP / DIGITAL TWIN</div>', unsafe_allow_html=True)
    st.title("Thermal Twin")
    page = st.radio("Workspace", ["Overview", "Thermal Twin", "Scenario Lab", "Performance Lab", "Configuration"], label_visibility="collapsed", key="sidebar_navigation")
    st.divider()
    st.caption("Simulation prototype · calculated temperatures, not live sensors")
    st.caption(f"{c['rows']} × {c['cols']} cells  ·  {c['solver'].upper()}")


def metrics():
    m = summarize(sim.temperature, c["hotspot_threshold"])
    cols = st.columns(4)
    cols[0].metric("Peak temperature", f"{m['max']:.2f} °C")
    cols[1].metric("Average temperature", f"{m['mean']:.2f} °C")
    cols[2].metric("Hotspot cells", f"{m['hotspot_count']:,}", f"{m['hotspot_pct']:.2f}%")
    cols[3].metric("Simulation clock", f"{sim.step * c['dt']:.0f} s", f"Step {sim.step}")


def run_steps(count: int):
    try:
        sim.advance(count)
    except Exception as exc:
        st.session_state.running = False
        st.error(str(exc))


if page == "Overview":
    st.markdown('<div class="eyebrow">ENGINEERING OVERVIEW</div>', unsafe_allow_html=True)
    st.title("Data center thermal state")
    st.caption("Two-dimensional transient heat model · fixed ambient boundary · simulated server load")
    metrics()
    if sim.step == 0:
        st.info("Sample configuration loaded. Open Thermal Twin to step the model or Configuration to create your own setup.")
    left, right = st.columns([1.7, 1])
    with left: st.plotly_chart(heatmap(sim.temperature), width="stretch")
    with right:
        st.subheader("Temperature history")
        st.plotly_chart(timeline(sim.history), width="stretch")
        t = timeline_metrics(sim.history, c["hotspot_threshold"], c["events"])
        recovery = f"{t['recovery_time_s']:.0f} s" if t["recovery_time_s"] is not None else "not measured"
        st.caption(f"Threshold: {c['hotspot_threshold']} °C · First crossing: {t['first_crossing_step'] or 'none'} · Time above: {t['hotspot_duration_s']:.0f} s · Recovery after restoration: {recovery}")
        st.write(f"Workload: **{c['pattern']}** · Solver: **{c['solver']}**")

elif page == "Thermal Twin":
    st.markdown('<div class="eyebrow">LIVE SIMULATION CONTROLS</div>', unsafe_allow_html=True)
    st.title("Thermal Twin")
    st.caption("Each step computes workload → power → heat → diffusion and cooling. The clock is simulated time.")
    b = st.columns([1,1,1,1,2])
    if b[0].button("Start / Resume", width="stretch"): st.session_state.running = True
    if b[1].button("Pause", width="stretch"): st.session_state.running = False
    if b[2].button("Step +1", width="stretch"): run_steps(1)
    if b[3].button("Reset", width="stretch"):
        st.session_state.running = False
        sim.reset()
    batch = b[4].number_input("Batch steps", min_value=1,max_value=500,value=10)
    if st.button("Run batch", type="primary"): run_steps(int(batch))
    st.caption(f"Status: {'running' if st.session_state.running else 'paused'} · Visual refresh: every step while running")
    @st.fragment(run_every="600ms")
    def live_panel():
        if st.session_state.running:
            run_steps(1)
        metrics()
        st.plotly_chart(heatmap(sim.temperature), width="stretch")
        st.plotly_chart(timeline(sim.history), width="stretch")
        st.download_button("Export temperature grid CSV", pd.DataFrame(sim.temperature).to_csv(index=False,header=False), "temperature-grid.csv", "text/csv")
        st.download_button("Export history CSV", pd.DataFrame(sim.history).to_csv(index=False), "temperature-history.csv", "text/csv")
    left, right = st.columns([2.2,1])
    with left:
        live_panel()
    with right:
        st.subheader("Selected cell")
        st.caption("Choose coordinates to inspect or change the next timestep's inputs.")
        row = st.number_input("Row", 0, c["rows"]-1, min(c["rows"]//2,c["rows"]-1))
        col = st.number_input("Column", 0, c["cols"]-1, min(c["cols"]//2,c["cols"]-1))
        row, col = int(row), int(col)
        u, power, _, cooling, _ = fields(c, sim.step, sim.overrides)
        st.write(f"**{sim.temperature[row,col]:.2f} °C** · {u[row,col]*100:.0f}% utilization")
        st.caption(f"Power {power[row,col]:.1f} W · Cooling {cooling[row,col]:.1f} W/(m³·K) · {'Hotspot' if sim.temperature[row,col]>c['hotspot_threshold'] else 'Below threshold'}")
        util = st.slider("Override utilization", 0.0,1.0,float(u[row,col]),0.01)
        cool = st.number_input("Override cooling", min_value=0.0,value=float(cooling[row,col]),step=1.0)
        if st.button("Apply to selected cell"):
            try: sim.set_cell(row,col,util,cool); st.success("Applied to the next step")
            except ValueError as exc: st.error(str(exc))
        st.divider()
        st.subheader("Scheduled events")
        kind = st.selectbox("Change", ["workload","cooling","redistribute","restore_cooling"])
        at = st.number_input("At step", min_value=0,value=sim.step+10)
        value = st.number_input("Value", min_value=0.0,value=0.9 if kind=="workload" else 10.0,disabled=kind in ("redistribute","restore_cooling"))
        if st.button("Schedule event"):
            event = {"step":int(at),"kind":kind}
            if kind in ("workload","cooling"): event["value"] = float(value)
            candidate = copy.deepcopy(c); candidate["events"].append(event)
            try: validate_config(candidate); c["events"].append(event); sim.config["events"].append(event); st.success("Event scheduled")
            except ValueError as exc: st.error(str(exc))
        if c["events"]: st.dataframe(pd.DataFrame(c["events"]),hide_index=True,width="stretch")

elif page == "Scenario Lab":
    st.markdown('<div class="eyebrow">CONTROLLED EXPERIMENTS</div>', unsafe_allow_html=True)
    st.title("Scenario Lab")
    st.caption("Saved configurations are reproducible. Comparisons start from the same initial field and use the same time horizon.")
    a,b = st.columns([1,2])
    with a:
        name = st.text_input("Scenario name", "My strategy")
        if st.button("Save current configuration"):
            try: st.success(f"Saved {save_scenario(name,c).name}")
            except ValueError as exc: st.error(str(exc))
        paths = list_scenarios()
        choices = {p.stem:p for p in paths}
        selected = st.selectbox("Saved scenario", ["Sample baseline"] + list(choices))
        if st.button("Load into Twin"):
            try:
                loaded = baseline_config() if selected == "Sample baseline" else load_scenario(choices[selected])
                st.session_state.config = loaded
                st.session_state.simulation = Simulation(loaded)
                st.session_state.running = False
                st.rerun()
            except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
                st.error(f"Cannot load scenario: {exc}")
        horizon = st.number_input("Comparison steps",min_value=1,max_value=500,value=120)
        compare = st.multiselect("Compare", ["Sample baseline","Current configuration"] + list(choices),
                                 default=["Sample baseline","Current configuration"])
        launch = st.button("Run comparison",type="primary",disabled=len(compare)<2)
    with b:
        if launch:
            results=[]; traces=[]
            bar=st.progress(0)
            for i,label in enumerate(compare):
                try:
                    conf = baseline_config() if label=="Sample baseline" else copy.deepcopy(c) if label=="Current configuration" else load_scenario(choices[label])
                    conf["steps"] = int(horizon)
                    if i:
                        keys=("rows","cols","initial_temp","ambient","dx","dy","rho_cp","conductivity","cell_volume","hotspot_threshold")
                        if any(conf[k]!=reference_config[k] for k in keys):
                            raise ValueError("comparison requires matching grid, initial field, model coefficients, and threshold")
                    else:
                        reference_config=conf
                    s=Simulation(conf); s.advance(int(horizon))
                    m=summarize(s.temperature,conf["hotspot_threshold"])
                    results.append({"scenario":label,"peak_°C":m["max"],"mean_°C":m["mean"],
                                    "hotspot_cells":m["hotspot_count"],"solver":conf["solver"]})
                    traces.append(pd.DataFrame(s.history).assign(scenario=label))
                except Exception as exc: st.error(f"{label}: {exc}")
                bar.progress((i+1)/len(compare))
            st.session_state.comparison = (results,traces)
        if "comparison" in st.session_state:
            results,traces=st.session_state.comparison
            st.dataframe(pd.DataFrame(results),hide_index=True,width="stretch")
            if traces:
                import plotly.express as px
                chart=px.line(pd.concat(traces),x="time_s",y="max",color="scenario",
                              labels={"time_s":"Simulation time (s)","max":"Peak temperature (°C)"})
                st.plotly_chart(chart,width="stretch")
                hot_chart=px.line(pd.concat(traces),x="time_s",y="hotspot_count",color="scenario",
                                  labels={"time_s":"Simulation time (s)","hotspot_count":"Hotspot cells"})
                st.plotly_chart(hot_chart,width="stretch")
            st.download_button("Export comparison CSV",pd.DataFrame(results).to_csv(index=False),"scenario-comparison.csv","text/csv")

elif page == "Performance Lab":
    st.markdown('<div class="eyebrow">PARALLEL COMPUTING</div>', unsafe_allow_html=True)
    st.title("Performance Lab")
    st.caption("Measured results only. Every solver receives the same initial state and constant input fields.")
    if "benchmarks" not in st.session_state:
        st.session_state.benchmarks=load_history()
    try: st.success(f"Native engine: {engine_path()}")
    except FileNotFoundError as exc: st.error(str(exc))
    info=environment_info()
    st.caption(f"CPU: {info['cpu']} · GPU: {info['gpu']} · CUDA compiler: {info['nvcc']}")
    col1,col2,col3,col4=st.columns(4)
    sizes=col1.multiselect("Square grid sizes",[32,64,100,250,500,1000,2000,4000],default=[64,100,250])
    steps=col2.number_input("Timesteps",min_value=1,max_value=10000,value=50)
    repeats=col3.number_input("Measured repeats",min_value=1,max_value=20,value=3)
    threads=col4.number_input("OpenMP threads",min_value=1,max_value=128,value=4)
    solvers=st.multiselect("Implementations",["cpu","openmp","cuda","cuda-shared"],default=["cpu","openmp"])
    block=st.selectbox("CUDA threads per block",[64,128,256,512,1024],index=2)
    estimate=max(sizes or [0])**2*4*5/(1024**2)
    st.caption(f"Approximate solver field memory at largest size: {estimate:.1f} MiB, plus process and GPU overhead. Large benchmarks can take time.")
    if st.button("Run measured benchmark",type="primary",disabled=not sizes or not solvers):
        bar=st.progress(0)
        try:
            df=benchmark(c,sizes,int(steps),solvers,int(repeats),int(threads),int(block),
                         lambda d,t:bar.progress(d/t))
            saved=save_results(df)
            st.success(f"Results saved to {saved}")
            if "benchmarks" in st.session_state:
                st.session_state.benchmarks=pd.concat([st.session_state.benchmarks,df],ignore_index=True)
            else:
                st.session_state.benchmarks=df
        except Exception as exc: st.error(str(exc))
    if not st.session_state.benchmarks.empty:
        df=st.session_state.benchmarks
        st.dataframe(df,width="stretch",hide_index=True)
        st.download_button("Export benchmark CSV",df.to_csv(index=False),"benchmark-results.csv","text/csv")
        metric=st.selectbox("Plot metric",["compute_time_ms","end_to_end_time_ms","speedup","throughput","max_absolute_error","kernel_time_ms","transfer_time_ms"])
        x,y=st.columns(2)
        with x: st.plotly_chart(benchmark_chart(df,metric),width="stretch")
        with y: st.plotly_chart(benchmark_chart(df,"speedup"),width="stretch")
        omp=df[(df["implementation"]=="openmp") & (df["success"]==True)]
        if not omp.empty and omp["thread_count"].nunique()>1:
            import plotly.express as px
            st.plotly_chart(px.line(omp,x="thread_count",y="compute_time_ms",color="grid_rows",markers=True,
                                    labels={"thread_count":"OpenMP threads","compute_time_ms":"Compute time (ms)"}),width="stretch")
    st.info("CUDA rows report a failure when the toolkit or a compatible build is unavailable. Driver detection alone does not count as a GPU benchmark.")

else:
    st.markdown('<div class="eyebrow">MODEL SETUP</div>', unsafe_allow_html=True)
    st.title("Configuration")
    st.caption("Changes become the new baseline when applied; the current simulation resets.")
    with st.form("config"):
        a,b,c3=st.columns(3)
        with a:
            st.subheader("Grid & time")
            rows=st.number_input("Rows",min_value=3,max_value=4000,value=c["rows"])
            cols=st.number_input("Columns",min_value=3,max_value=4000,value=c["cols"])
            dt=st.number_input("Timestep (s)",min_value=0.001,value=float(c["dt"]))
            dx=st.number_input("Cell width dx (m)",min_value=0.001,value=float(c["dx"]))
            dy=st.number_input("Cell width dy (m)",min_value=0.001,value=float(c["dy"]))
            initial=st.number_input("Initial temperature (°C)",value=float(c["initial_temp"]))
            ambient=st.number_input("Boundary ambient (°C)",value=float(c["ambient"]))
        with b:
            st.subheader("Thermal physics")
            rho_cp=st.number_input("Volumetric heat capacity (J/m³/K)",min_value=0.001,value=float(c["rho_cp"]))
            conductivity=st.number_input("Effective conductivity (W/m/K)",min_value=0.0,value=float(c["conductivity"]))
            air=st.number_input("Cooling air (°C)",value=float(c["air_temp"]))
            cooling=st.number_input("Cooling coefficient (W/m³/K)",min_value=0.0,value=float(c["cooling"]))
            volume=st.number_input("Effective cell volume (m³)",min_value=0.001,value=float(c["cell_volume"]))
            idle=st.number_input("Idle power (W)",min_value=0.0,value=float(c["idle_power"]))
            maximum=st.number_input("Maximum power (W)",min_value=0.0,value=float(c["max_power"]))
            threshold=st.number_input("Hotspot threshold (°C)",value=float(c["hotspot_threshold"]))
        with c3:
            st.subheader("Load & execution")
            pattern=st.selectbox("Workload pattern",PATTERNS,index=PATTERNS.index(c["pattern"]))
            utilization=st.slider("Base utilization",0.0,1.0,float(c["base_utilization"]))
            amplitude=st.slider("Variation amplitude",0.0,1.0,float(c["amplitude"]))
            period=st.number_input("Periodic interval (steps)",min_value=1,value=c["period"])
            seed=st.number_input("Random seed",min_value=0,value=c["seed"])
            spike=st.number_input("Spike start step",min_value=0,value=c["spike_start"])
            spike_u=st.slider("Spike utilization",0.0,1.0,float(c["spike_utilization"]))
            failure=st.number_input("Cooling failure start",min_value=0,value=c["failure_start"])
            factor=st.slider("Failure cooling factor",0.0,1.0,float(c["failure_factor"]))
            solver=st.selectbox("Solver",["cpu","openmp","cuda","cuda-shared"],index=["cpu","openmp","cuda","cuda-shared"].index(c["solver"]))
            nthreads=st.number_input("CPU threads",min_value=1,max_value=128,value=c["threads"])
            block_size=st.selectbox("CUDA block size",[64,128,256,512,1024],index=[64,128,256,512,1024].index(c["block_size"]))
        st.subheader("Localized region")
        r1,r2,r3,r4=st.columns(4)
        rr=r1.number_input("Top row",0,int(rows)-1,min(c["region"]["row"],int(rows)-1))
        rc=r2.number_input("Left column",0,int(cols)-1,min(c["region"]["col"],int(cols)-1))
        rh=r3.number_input("Height",1,int(rows)-int(rr),min(c["region"]["height"],int(rows)-int(rr)))
        rw=r4.number_input("Width",1,int(cols)-int(rc),min(c["region"]["width"],int(cols)-int(rc)))
        apply=st.form_submit_button("Apply configuration",type="primary")
    if apply:
        candidate=copy.deepcopy(c)
        candidate.update(rows=int(rows),cols=int(cols),dt=dt,dx=dx,dy=dy,initial_temp=initial,
                         ambient=ambient,rho_cp=rho_cp,conductivity=conductivity,air_temp=air,
                         cooling=cooling,cell_volume=volume,idle_power=idle,max_power=maximum,
                         hotspot_threshold=threshold,pattern=pattern,base_utilization=utilization,
                         amplitude=amplitude,period=int(period),seed=int(seed),spike_start=int(spike),
                         spike_utilization=spike_u,failure_start=int(failure),failure_factor=factor,
                         solver=solver,threads=int(nthreads),block_size=block_size,
                         region={"row":int(rr),"col":int(rc),"height":int(rh),"width":int(rw)})
        try:
            validate_config(candidate)
            st.session_state.config=candidate
            st.session_state.simulation=Simulation(candidate)
            st.session_state.running=False
            st.success("Configuration applied; simulation reset")
        except ValueError as exc: st.error(str(exc))
    st.info("Model: ρcp ∂T/∂t = k∇²T + P/V − h(T−T_air). Boundary cells stay at ambient temperature. These are effective parameters for a teaching prototype; no facility calibration or live sensors are included.")
    st.download_button("Export configuration JSON",json.dumps(c,indent=2),"thermal-config.json","application/json")
