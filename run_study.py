
import pandas as pd
from pommes.io.build_input_dataset import *
from pommes.model.data_validation.dataset_check import check_inputs
from pommes.io.save_solution import save_solution
from pommes.model.build_model import build_model
import warnings
import time
from datetime import timedelta
import getopt, sys

warnings.filterwarnings("ignore")

all_areas=['AL', 'AT', 'BA', 'BE', 'BG', 'CH', 'CZ', 'DE', 'DK', 'EE', 'ES',
       'FI', 'FR', 'GR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MD', 'ME',
       'MK', 'MT', 'NL', 'NO', 'PL', 'PT', 'RO', 'RS', 'SE', 'SI', 'SK','UK']
###
# Default parameters
###
solver = "cplex"  # gurobi, cplex, mosek, highs
threads = 4
h2_mr=False
daily_h2_demand=False
industry_hubs=False
belgian_backbone_setting=0
config_file="config.yaml"
areas=["BE","NL","FR","DE","UK","LU","ES","PT","IT","CH","IE","DK","NO","SE","SI","PL",
        "CZ","AT","EE","LV","LT","FI","HU","RO","SK","BG","GR"]
##########################
args = sys.argv[1:]
# print(args)
options = "s:c:t:n:mdhb:"
long_options = ["solver", "config_file", "threads","nodes","must_run_h2","daily_h2_demand","hubs_industry","belgian_backbone_setting"]
go=True
try:
    arguments, values = getopt.getopt(args, options, long_options)
    # print(arguments)
    for currentArg, currentVal in arguments:
        if currentArg in ("-s", "--solver"):
            solver = currentVal
            print("Solver set to " + solver)
        elif currentArg in ("-c", "--config_file"):
            config_file = currentVal
            print("Config file:", config_file)
        elif currentArg in ("-t", "--threads"):
            threads = int(currentVal)
            print("Threads:", threads)
        elif currentArg in ("-n", "--nodes"):
            areas = areas[:int(currentVal)]
            print("Nodes:", areas)
        elif currentArg in ("-m", "--must_run_h2"):
            h2_mr=True
            print("Hydrogen Must Run set")
        elif currentArg in ("-d", "--daily_h2_demand"):
            daily_h2_demand=True
            print("Daily hydrogen demand set")
        elif currentArg in ("-h", "--hubs_industry"):
            industry_hubs=True
            areas+=["Liege","AlbertCanal","Charleroi","Antwerp","Ghent","Tournai_Mons"]
            if config_file!="config.yaml":
                areas+=["Zeebrugge"]
            print("Industry hubs set")
        elif currentArg in ("-b", "--belgian_backbone_setting"):
            if not industry_hubs:
                print("Belgian Backbone requires industry hubs to be set")
                go = False
            elif int(currentVal) not in [0,1,2]:
                print("Invalid Belgian Backbone configuration set - needs to be in [0,1,2]")
                go = False
            else:
                belgian_backbone_setting=int(currentVal)
                if int(currentVal)==2:
                    areas+=["BE_cavern"]
    if industry_hubs+daily_h2_demand+h2_mr>1:
        go=False
        print("Invalid scenario set")
except getopt.error as err:
    print(str(err))
    go=False

if __name__ == "__main__" and go:


        title=f"\033[1m Running POMMES-EU \033[0m"

        print(title)




        year_op=[2050]


        if areas==["all"]:
            areas=all_areas


        add=""
        if len(year_op)<4*3:
            for i in year_op:
                add+="-"+str(i)
        suffix = f"{len(areas)}-nodes"+add
        if len(areas)==1:
            suffix=f"{areas[0]}"+add
        elif len(areas)==2:
            suffix = f"{areas[0]}-{areas[1]}" + add
        if config_file[7:-5]!='':
            suffix+='-'+config_file[7:-5]
        if h2_mr:
            suffix+='-h2_mr'
        if daily_h2_demand:
            suffix+='-daily_h2_demand'
        if industry_hubs:
            suffix+=f"-bhb_{belgian_backbone_setting}"

        print(suffix)
        print(year_op,areas)
        output_folder = f"output/{suffix}"

        start = time.time()
        print("\033[1m Input data load and pre-processing \033[0m")
        config = read_config_file(file_path=config_file)
        config["input"]["path"] = "data"
        config["coords"]["area"]["values"]=areas
        config["coords"]["year_op"]["values"] = year_op


        ####Link adjustment
        if config["add_modules"]["transport"] :
            areas=config["coords"]["area"]["values"]
            if not industry_hubs:
                all_links=pd.read_csv(config["input"]["path"]+"/transport_link.csv",sep=";").link.unique()
            else:
                all_links = pd.read_csv(config["input"]["path"] + "/transport_link_indhub.csv", sep=";").link.unique()
            links = []

            for link in all_links:
                pos = ""
                i = 0
                while pos != "-":
                    pos = link[i]
                    i += 1
                area_from = link[:i - 1]
                area_to = link[i:]
                if area_to in areas and area_from in areas:
                    links.append(link)
            if len(links) >= 1:
                config["coords"]["link"]["values"] = links
            else:
                config["add_modules"]["transport"]=False
        print("\t Transport activated:", config["add_modules"]["transport"])

        #####Hydrogen must run setting
        if h2_mr:
            for param in ["conversion_max_yearly_production","conversion_max_daily_production",
                          "conversion_power_capacity_max","conversion_power_capacity_min",
                          "conversion_fixed_cost","conversion_variable_cost","conversion_must_run"]:
                config["input"]["parameters"][param]["file"]=config["input"]["parameters"][param]["file"][:-4] + "_h2_must_run" + config["input"]["parameters"][param]["file"][-4:]
        #####Daily hydrogen demand setting
        if daily_h2_demand:
            config["input"]["parameters"]["demand"]["file"]="demand_dh2d.csv"
            config["input"]["parameters"]["flexdem_demand"]["file"] = "flexdem_demand_dh2d.csv"
            for param in ["flexdem_conservation_hrs","flexdem_ramp_up","flexdem_ramp_down","flexdem_maxload_ratio","flexdem_minload_ratio"]:
                config["input"]["parameters"][param]["file"]="flexdem_op_dh2d.csv"

        #####Industry hubs setting
        if industry_hubs:
            #conversion_op2 update
            for param in ["conversion_max_yearly_production","conversion_max_daily_production",
                          "conversion_power_capacity_max","conversion_power_capacity_min",
                          "conversion_fixed_cost","conversion_variable_cost","conversion_must_run"]:
                config["input"]["parameters"][param]["file"]=config["input"]["parameters"][param]["file"][:-4] + "_indhub" + config["input"]["parameters"][param]["file"][-4:]

            #demand update
            config["input"]["parameters"]["demand"]["file"]="demand_indhub.csv"

            #transport_tech list update
            transport_tech_list = ["hvac", "hvdc", "local_tso", "local_biogas"]
            if belgian_backbone_setting > 0:  # if setting 0 then no BHB
                transport_tech_list += ["h2_pipeline"]
            config["coords"]["transport_tech"]["values"] = transport_tech_list

            #transport and storage_in2 files update
            transport_suffix = "_indhub"
            transport_op2_suffix = transport_suffix
            storage_suffix="_indhub"
            if config_file=="config.yaml":
                transport_op2_suffix+="_isolated"
                storage_suffix += "_isolated"
                if belgian_backbone_setting>0:
                    storage_tech_list=["battery", "PHS","h2_tank","salt_cavern","hydro_reservoir_volume","hydro_pondage_volume"]
                    config["coords"]["storage_tech"]["values"]=storage_tech_list

            for param in ["storage_energy_capacity_investment_max","storage_energy_capacity_investment_min","storage_power_capacity_investment_max","storage_power_capacity_investment_min"]:
                config["input"]["parameters"][param]["file"] = f"storage_inv2{storage_suffix}.csv"

            for param in ["transport_annuity_perfect_foresight","transport_early_decommissioning",
                          "transport_invest_cost","transport_life_span","transport_finance_rate"]:
                config["input"]["parameters"][param]["file"] = f"transport_inv{transport_suffix}.csv"

            for param in ["transport_area_from","transport_area_to","transport_resource"]:
                config["input"]["parameters"][param]["file"] = f"transport_link{transport_suffix}.csv"

            for param in ["transport_power_capacity_max","transport_power_capacity_min"]:
                config["input"]["parameters"][param]["file"] = f"transport_op2{transport_op2_suffix}.csv"


        model_parameters = build_input_parameters(config)
        model_parameters = check_inputs(model_parameters)

        print("\033[1m Model building \033[0m")
        start_build = time.time()
        model = build_model(model_parameters)



        elapsed_time = time.time() - start_build
        print("\t Model building took {}".format(timedelta(seconds=elapsed_time)))

        print("\033[1m Model solving \033[0m")
        if solver == "gurobi":
            model.solve(solver_name="gurobi", #progress=True,
                        io_api='direct',
                        threads=threads, method=2,barhomogeneous=1,crossover=0,
                        nodefilestart=0.1, presparsify=2, presolve=2,#memlimit=8,
                        logtoconsole=1, outputflag=1
                        )
        elif solver=="cplex":
            solver_options={"threads":threads,"preprocessing.presolve":1,"lpmethod":4,
                            # 'barrier.convergetol':5e-5
                            }
            model.solve(solver_name="cplex",**solver_options) #parameters={"presolve":1} epfi=1e-5,
        elif solver=="highs":
            model.solve(solver_name="highs",presolve='on',solver='ipx',run_crossover='choose')

        else:
            model.solve(solver_name=solver, threads=threads)

        converge = True
        print(model.termination_condition )
        if model.termination_condition not in ["optimal","suboptimal"]:
            try:
                print("\t Searching for infeasabilities")
                model.compute_infeasibilities()
                model.print_infeasibilities()
                converge = False
            except:
                converge = False
        if converge:
            print("\033[1m Results export \033[0m")
            save_solution(
                model=model,
                output_folder=output_folder,
                save_model=False,
                export_csv=False,
                model_parameters=model_parameters,
            )

            elapsed_time = time.time() - start
            print("Process took {}".format(timedelta(seconds=elapsed_time)))

        del model
        del model_parameters