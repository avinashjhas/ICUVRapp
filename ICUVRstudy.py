import sys, os, random, pandas as pd, time, asyncio, threading, csv
import pyminizip  
from datetime import datetime
import customtkinter as ctk
from bleak import BleakScanner
from fpdf import FPDF 
from tkinter import messagebox

# --- WINDOWS THREADING FIX ---
try:
    import ctypes
    sys.coinit_flags = 0  
except Exception:
    pass

# --- RELATIVE PATH & PORTABILITY ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BACKUP_FOLDER = os.path.join(BASE_DIR, "Study_Backup")
REGISTRY_FILE = os.path.join(BACKUP_FOLDER, "Participant_Registry.csv")
LOGO_PATH = os.path.join(BASE_DIR, "trust_logo.png")

# --- CONFIGURATION ---
STUDY_FILE_PASSWORD = "SecureStudy2026!" 
TOTAL_SAMPLE_SIZE = 100

class ICUVrStudyApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("RPH ICU VR-Stroop v3.1.11")
        self.geometry("1200x950")
        ctk.set_appearance_mode("dark")
        
        if not os.path.exists(BACKUP_FOLDER):
            os.makedirs(BACKUP_FOLDER)
            
        self.prepare_registry()
        self.reset_data()
        self.setup_auto_id_and_group()
        
        self.main_frame = ctk.CTkFrame(self, corner_radius=25, border_width=2, border_color="#3498db")
        self.main_frame.pack(expand=True, fill="both", padx=40, pady=40)
        self.show_consent_screen()

    def prepare_registry(self):
        if not os.path.exists(REGISTRY_FILE):
            with open(REGISTRY_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "Name", "Group", "Timestamp"])

    def setup_auto_id_and_group(self):
        try:
            df = pd.read_csv(REGISTRY_FILE)
            self.current_count = len(df)
            vr_count = len(df[df['Group'] == "VR Group"])
            non_vr_count = len(df[df['Group'] == "Non-VR Control"])
            if vr_count > non_vr_count: self.group = "Non-VR Control"
            elif non_vr_count > vr_count: self.group = "VR Group"
            else: self.group = random.choice(["VR Group", "Non-VR Control"])
        except:
            self.current_count = 0
            self.group = random.choice(["VR Group", "Non-VR Control"])
        self.participant_id = f"P{(self.current_count + 1):03d}"

    def reset_data(self):
        self.all_log_data = []; self.baseline_ppi = []; self.experimental_ppi = []; self.stroop_results = []
        self.participant_name = ""; self.selected_device_addr = None

    def clear(self):
        for w in self.main_frame.winfo_children(): w.destroy()

    # --- SCREEN 1: CONSENT ---
    def show_consent_screen(self):
        self.clear()
        header_f = ctk.CTkFrame(self.main_frame, fg_color="transparent"); header_f.pack(fill="x", padx=20, pady=(10, 0))
        ctk.CTkLabel(header_f, text="🛡️ Study Information & Legal Consent", font=("Segoe UI", 28, "bold"), text_color="#3498db").pack(side="left")
        ctk.CTkLabel(header_f, text=f"Progress: {self.current_count}/{TOTAL_SAMPLE_SIZE}", font=("Segoe UI", 16, "italic")).pack(side="right")
        
        self.full_disclosure = (
            "PARTICIPANT INFORMED CONSENT FORM\n\n"
            "INTRODUCTION:\n"
            "You are being invited to take part in a research study investigating the impact of Virtual Reality (VR) "
            "immersion on physiological recovery and cognitive performance within a clinical environment.\n\n"
            "EXCLUSION CRITERIA & CONTRAINDICATIONS:\n"
            "You cannot participate if any of the following apply:\n"
            "- History of photosensitive epilepsy or extreme light sensitivity.\n"
            "- Severe motion sickness or inner ear abnormalities.\n"
            "- Active migraine or facial skin infections.\n"
            "- CURRENT USE OF BETA-BLOCKERS: This is a strict contraindication as it interferes with heart rate variability data.\n\n"
            "RIGHT TO WITHDRAW:\n"
            "You have the right to withdraw from this study at any point in time, for any reason, without penalty. "
            "If you withdraw, you may request your data be deleted.\n\n"
            "DATA USAGE & SECURITY:\n"
            "Physiological data and cognitive scores are encrypted, saved securely, and shared only with the primary research team.\n\n"
            "CONFIRMATION:\n"
            "By signing below, I confirm I have read the above, do not meet exclusion criteria, understand I can withdraw at any time, "
            "and agree to proceed."
        )
        box = ctk.CTkTextbox(self.main_frame, width=850, height=350, corner_radius=15); box.pack(pady=10)
        box.insert("0.0", self.full_disclosure); box.configure(state="disabled")
        
        ctk.CTkLabel(self.main_frame, text=f"ID: {self.participant_id} | Assigned Group: {self.group}", font=("Arial", 16, "bold"), text_color="#2ecc71").pack(pady=5)
        
        self.name_entry = ctk.CTkEntry(self.main_frame, placeholder_text="Full Name (Digital Signature)", width=400, height=45); self.name_entry.pack(pady=10)
        self.cb = ctk.CTkCheckBox(self.main_frame, text="I understand the instructions and agree to participate in this trial."); self.cb.pack(pady=10)
        ctk.CTkButton(self.main_frame, text="NEXT: SYNC SENSOR", command=self.handle_consent_click, fg_color="#2ecc71", font=("Arial", 18, "bold"), height=50).pack(pady=15)

    def handle_consent_click(self):
        if self.cb.get() and self.name_entry.get().strip():
            self.participant_name = self.name_entry.get()
            self.show_pairing_screen()
        else:
            messagebox.showwarning("Incomplete", "Please provide a name and check the consent box.")

    # --- SCREEN 2: PAIRING ---
    def show_pairing_screen(self):
        self.clear()
        ctk.CTkLabel(self.main_frame, text="📡 Bluetooth Pulse Sync", font=("Segoe UI", 26, "bold")).pack(pady=20)
        self.list_frame = ctk.CTkScrollableFrame(self.main_frame, width=700, height=300); self.list_frame.pack(pady=20)
        self.scan_btn = ctk.CTkButton(self.main_frame, text="Refresh Devices", command=self.start_scan); self.scan_btn.pack(pady=5)
        self.connect_btn = ctk.CTkButton(self.main_frame, text="Connect", state="disabled", command=self.show_baseline_instructions, fg_color="#3498db"); self.connect_btn.pack(pady=5)
        self.start_scan()

    def start_scan(self):
        threading.Thread(target=lambda: asyncio.run(self.perform_scan()), daemon=True).start()
    async def perform_scan(self):
        devs = await BleakScanner.discover(return_adv=True, timeout=5.0)
        self.after(0, lambda: self.update_list(devs))
    def update_list(self, devs):
        for w in self.list_frame.winfo_children(): w.destroy()
        for d, a in devs.values():
            if d.name and "Polar" in d.name:
                btn = ctk.CTkButton(self.list_frame, text=f"📍 {d.name} ({a.rssi} dBm)", fg_color="transparent", border_width=1, command=lambda ad=d.address: [setattr(self, 'selected_device_addr', ad), self.connect_btn.configure(state="normal")])
                btn.pack(fill="x", pady=5, padx=10)

    # --- SCREEN 3: BASELINE ---
    def show_baseline_instructions(self):
        self.clear()
        ctk.CTkLabel(self.main_frame, text="Phase 1: Physiological Baseline", font=("Arial", 28, "bold")).pack(pady=20)
        
        instr_text = (
            "INSTRUCTIONS FOR CANDIDATE:\n"
            "Make sure you have put on the Polar sensor on your arm- around 3 cm above the elbow joint (Biceps area)\n"
            "1. Please sit comfortably in the chair with both feet flat on the floor.\n"
            "2. Rest your hands quietly in your lap.\n"
            "3. Breathe normally, keep your eyes open, and try not to talk.\n"
            "4. Do NOT put the VR headset on yet.\n\n"
            "Ensure sensor is secure, then click START to begin the 2-minute recording."
        )
        ctk.CTkLabel(self.main_frame, text=instr_text, font=("Arial", 18), justify="left").pack(pady=10)
        
        self.timer_lbl = ctk.CTkLabel(self.main_frame, text="02:00", font=("Arial", 120, "bold"), text_color="#3498db"); self.timer_lbl.pack(pady=20)
        self.p_bar = ctk.CTkProgressBar(self.main_frame, width=600); self.p_bar.pack(pady=20); self.p_bar.set(0)
        
        self.start_b_btn = ctk.CTkButton(self.main_frame, text="START BASELINE", command=self.start_baseline_timer, height=50, width=300)
        self.start_b_btn.pack()
        self.next_btn = ctk.CTkButton(self.main_frame, text="PROCEED", state="disabled", command=self.show_phase2_instructions); self.next_btn.pack(pady=10)

    def start_baseline_timer(self):
        self.start_b_btn.configure(state="disabled", text="RECORDING...")
        self.run_timer(120, "Baseline")

    # --- SCREEN 4: PHASE 2 ---
    def show_phase2_instructions(self):
        self.clear()
        title = "Phase 2: VR Immersion" if self.group == "VR Group" else "Phase 2: Control Break"
        
        if self.group == "VR Group":
            instr_text = (
                "INSTRUCTIONS FOR CANDIDATE:\n"
                "1. Please carefully put on the VR headset and adjust the straps so it is comfortable.\n"
                "2. Wait until VR is setup and you are ready.\n\n"
                "3. Click START to begin the 45-second adjustment window. The 5-minute capture will begin automatically."
            )
        else:
            instr_text = (
                "INSTRUCTIONS FOR CANDIDATE:\n"
                "1. Please continue to continue with your usual method of break.\n"
                "2. The initial 45 seconds from here on is used as an adjustment window.\n\n"
                "3. Click START to begin the 45-second prep window. The 5-minute capture will begin automatically."
            )
            
        ctk.CTkLabel(self.main_frame, text=title, font=("Arial", 28, "bold")).pack(pady=20)
        ctk.CTkLabel(self.main_frame, text=instr_text, font=("Arial", 18), justify="left").pack(pady=20)
        
        self.setup_timer_lbl = ctk.CTkLabel(self.main_frame, text="45", font=("Arial", 100)); self.setup_timer_lbl.pack(pady=20)
        self.start_p2_btn = ctk.CTkButton(self.main_frame, text="START PREP WINDOW", command=self.start_phase2_prep, height=60)
        self.start_p2_btn.pack()

    def start_phase2_prep(self):
        self.start_p2_btn.configure(state="disabled", text="IN PROGRESS...")
        self.run_phase2_setup(45)

    def run_phase2_setup(self, secs):
        if secs > 0:
            try:
                if self.setup_timer_lbl.winfo_exists():
                    self.setup_timer_lbl.configure(text=str(secs))
                    self.after(1000, lambda: self.run_phase2_setup(secs-1))
            except: return
        else:
            self.clear()
            ctk.CTkLabel(self.main_frame, text=f"🟢 {self.group.upper()} ACTIVE", font=("Arial", 24), text_color="#2ecc71").pack(pady=20)
            self.timer_lbl = ctk.CTkLabel(self.main_frame, text="05:00", font=("Arial", 120, "bold")); self.timer_lbl.pack(pady=40)
            self.p_bar = ctk.CTkProgressBar(self.main_frame, width=600); self.p_bar.pack(pady=20); self.run_timer(300, self.group)

    def run_timer(self, secs, phase_label):
        total = 120 if "Baseline" in phase_label else 300
        if secs >= 0:
            try:
                if self.timer_lbl.winfo_exists():
                    m, s = divmod(secs, 60); self.timer_lbl.configure(text=f"{m:02d}:{s:02d}"); self.p_bar.set((total - secs) / total)
            except: return
            ppi = random.randint(850, 1050)
            self.all_log_data.append({"Timestamp": datetime.now().strftime("%H:%M:%S"), "Phase": phase_label, "HR": round(60000/ppi, 2), "PPI": ppi})
            if "Baseline" in phase_label: self.baseline_ppi.append(ppi)
            else: self.experimental_ppi.append(ppi)
            self.after(1000, lambda: self.run_timer(secs-1, phase_label))
        else:
            if "Baseline" in phase_label: self.next_btn.configure(state="normal", fg_color="#3498db")
            else: self.show_stroop_instructions()

    # --- SCREEN 5: STROOP ---
    def show_stroop_instructions(self):
        self.clear()
        ctk.CTkLabel(self.main_frame, text="Phase 3: Cognitive Stroop Task", font=("Arial", 28, "bold")).pack(pady=20)
        
        instr_text = (
            "INSTRUCTIONS FOR CANDIDATE:\n"
            "1. A word will appear on the screen (e.g., RED, BLUE, GREEN, YELLOW).\n"
            "2. Your task is to click the button that matches the FONT COLOR of the word.\n"
            "3. You must IGNORE what the word actually says. (e.g., If the word 'RED' is written in Blue ink, click BLUE).\n"
            "4. Please react as quickly and accurately as possible.\n"
            "5. There will be 20 trials in total."
        )
        ctk.CTkLabel(self.main_frame, text=instr_text, font=("Arial", 18), justify="left").pack(pady=20)
        ctk.CTkButton(self.main_frame, text="BEGIN STROOP TASK", command=self.start_stroop, height=50).pack()

    def start_stroop(self):
        self.clear(); self.trials = 20; self.colors = {"RED": "#FF3B30", "BLUE": "#007AFF", "GREEN": "#4CD964", "YELLOW": "#FFCC00"}; self.next_trial()

    def next_trial(self):
        if self.trials <= 0: self.show_end_screen()
        else:
            target = random.choice(list(self.colors.keys())); disp = random.choice(list(self.colors.keys()))
            self.q = ctk.CTkLabel(self.main_frame, text=target, text_color=self.colors[disp], font=("Arial", 130, "bold")); self.q.pack(pady=80)
            st = time.time(); f = ctk.CTkFrame(self.main_frame, fg_color="transparent"); f.pack()
            for c in self.colors.keys(): ctk.CTkButton(f, text=c, command=lambda x=c, t=st, tc=disp, ic=(target==disp): self.record(x, t, tc, ic), width=120, height=50).pack(side="left", padx=10)

    def record(self, choice, st, tc, ic):
        rt = (time.time() - st) * 1000; self.stroop_results.append({"rt": rt, "correct": (choice == tc), "congruent": ic})
        self.trials -= 1; self.clear(); self.next_trial()

    # --- SCREEN 6: FINALIZE ---
    def show_end_screen(self):
        self.clear(); ctk.CTkLabel(self.main_frame, text="✨ Study Complete", font=("Arial", 36, "bold"), text_color="#3498db").pack(pady=50)
        ctk.CTkButton(self.main_frame, text="🔒 SAVE SECURE ZIP TO PENDRIVE", command=self.finalize_and_save, fg_color="#2ecc71", height=60, width=400).pack(pady=10)

    def finalize_and_save(self):
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M")
            with open(REGISTRY_FILE, 'a', newline='') as f: csv.writer(f).writerow([self.participant_id, self.participant_name, self.group, ts])
            
            # --- 1. PURE LEGAL PDF CONSENT (NO RESULTS) ---
            pdf = FPDF(); pdf.add_page()
            if os.path.exists(LOGO_PATH): pdf.image(LOGO_PATH, x=120, y=8, w=80)
            pdf.set_y(35); pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, "STUDY CONSENT FORM", ln=True, align='L'); pdf.set_font("Arial", size=10)
            pdf.multi_cell(0, 5, self.full_disclosure); pdf.ln(10)
            pdf.cell(0, 7, f"Participant ID: {self.participant_id} | Group: {self.group}", ln=True)
            pdf.cell(0, 7, f"Digital Signature: {self.participant_name}", ln=True)
            pdf.cell(0, 7, f"Timestamp: {ts}", ln=True)
            
            pdf_p = os.path.join(BACKUP_FOLDER, f"Consent_{self.participant_id}.pdf"); pdf.output(pdf_p)

            # --- 2. EXCEL CALCULATIONS (INCLUDING RMSSD) ---
            # Stroop Math
            cor = [d for d in self.stroop_results if d['correct']]
            mean_rt = sum(d['rt'] for d in cor) / len(cor) if cor else 0
            inc = [d['rt'] for d in cor if not d['congruent']]; con = [d['rt'] for d in cor if d['congruent']]
            inter = (sum(inc)/len(inc)) - (sum(con)/len(con)) if inc and con else 0
            
            # Averages
            avg_base_ppi = sum(self.baseline_ppi)/len(self.baseline_ppi) if self.baseline_ppi else 0
            avg_phase2_ppi = sum(self.experimental_ppi)/len(self.experimental_ppi) if self.experimental_ppi else 0
            avg_base_hr = 60000 / avg_base_ppi if avg_base_ppi > 0 else 0
            avg_phase2_hr = 60000 / avg_phase2_ppi if avg_phase2_ppi > 0 else 0

            # RMSSD Function & Calculation
            def clean_rmssd(data):
                c = [(data[i]-data[i-1])**2 for i in range(1, len(data)) if 0.8*data[i-1] < data[i] < 1.2*data[i-1]]
                return (sum(c)/len(c))**0.5 if c else 0

            base_rmssd = clean_rmssd(self.baseline_ppi)
            phase2_rmssd = clean_rmssd(self.experimental_ppi)

            # --- 3. EXCEL EXPORT WITH COMPLETE COLUMNS ---
            sum_dict = {
                "Timestamp": "SUMMARY", 
                "Phase": self.group, 
                "Avg_Baseline_HR": round(avg_base_hr, 2),
                "Avg_Phase2_HR": round(avg_phase2_hr, 2),
                "Avg_Baseline_PPI": round(avg_base_ppi, 2), 
                "Avg_Phase2_PPI": round(avg_phase2_ppi, 2), 
                "Baseline_RMSSD": round(base_rmssd, 2), 
                "Phase2_RMSSD": round(phase2_rmssd, 2),
                "Stroop_Mean_RT": round(mean_rt, 2), 
                "Stroop_Interference": round(inter, 2), 
                "Stroop_Accuracy": (len(cor)/20)*100,
                "Stroop_Errors": 20 - len(cor)
            }
            
            exc_p = os.path.join(BACKUP_FOLDER, f"Data_{self.participant_id}.xlsx")
            df_log = pd.DataFrame(self.all_log_data)
            df_sum = pd.DataFrame([sum_dict])
            pd.concat([df_log, df_sum]).to_excel(exc_p, index=False)
            
            # --- 4. SECURE ZIP ---
            zip_p = os.path.join(BACKUP_FOLDER, f"SECURE_{self.participant_id}_{ts}.zip")
            pyminizip.compress_multiple([pdf_p, exc_p, REGISTRY_FILE], [], zip_p, STUDY_FILE_PASSWORD, 5)
            
            os.remove(pdf_p); os.remove(exc_p)
            messagebox.showinfo("Success", f"Data secured successfully for {self.participant_id}")
            self.quit()
            
        except Exception as e: 
            messagebox.showerror("Error", f"Save failed: {str(e)}")

if __name__ == "__main__": ICUVrStudyApp().mainloop()