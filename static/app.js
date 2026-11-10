const { createApp } = Vue;

// Small helper: every API call goes through here so the token is attached automatically.
async function api(url, method = "GET", body = null) {
  const headers = { "Content-Type": "application/json" };
  const token = localStorage.getItem("token");
  if (token) headers["Authorization"] = "Bearer " + token;

  const res = await fetch(url, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null,
  });
  if (res.status === 401 && token) {
    localStorage.clear();
    location.reload();
    return;
  }
  const data = await res.json();
  if (!res.ok)
    throw new Error(data.error || data.msg || "Something went wrong");
  return data;
}

const AuthPage = {
  emits: ["logged-in"],
  data() {
    return {
      mode: "login",
      name: "",
      email: "",
      password: "",
      phone: "",
      error: "",
      success: "",
    };
  },
  methods: {
    async submit() {
      this.error = "";
      this.success = "";
      try {
        if (this.mode === "register") {
          await api("/api/register", "POST", {
            name: this.name,
            email: this.email,
            password: this.password,
            phone: this.phone,
          });
          this.success = "Registered! Please log in.";
          this.mode = "login";
        } else {
          const data = await api("/api/login", "POST", {
            email: this.email,
            password: this.password,
          });
          localStorage.setItem("token", data.token);
          localStorage.setItem("user", JSON.stringify(data.user));
          this.$emit("logged-in", data.user);
        }
      } catch (e) {
        this.error = e.message;
      }
    },
  },
  template: `
  <div class="container" style="max-width:420px; margin-top:80px;">
    <div class="card shadow-sm"><div class="card-body p-4">
      <h4 class="mb-3 text-center">{{ mode === 'login' ? 'Login' : 'Register' }}</h4>
      <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
      <div v-if="success" class="alert alert-success py-2">{{ success }}</div>
      <form @submit.prevent="submit">
        <input v-if="mode==='register'" v-model="name" class="form-control mb-3" placeholder="Name" required>
        <input v-model="email" type="email" class="form-control mb-3" placeholder="Email" required>
        <input v-if="mode==='register'" v-model="phone" class="form-control mb-3" placeholder="Phone (optional)">
        <input v-model="password" type="password" class="form-control mb-3" placeholder="Password" minlength="6" required>
        <button class="btn btn-primary w-100">{{ mode === 'login' ? 'Login' : 'Register' }}</button>
      </form>
      <p class="text-center mt-3 mb-0">
        <a href="#" @click.prevent="mode = (mode==='login' ? 'register' : 'login')">
          {{ mode === 'login' ? 'New trekker? Register' : 'Already registered? Login' }}
        </a>
      </p>
    </div></div>
  </div>`,
};

function emptyTrek() {
  return { name: "", location: "", difficulty: "Easy", duration: 1, total_slots: 10,
           status: "Pending", start_date: "", end_date: "", instructions: "" };
}

const AdminPanel = {
  data() {
    return {
      tab: "overview", stats: {}, treks: [], users: [], staff: [], bookings: [],
      q: "", error: "", msg: "",
      form: emptyTrek(), editingId: null, showForm: false,
      staffForm: { name: "", email: "", password: "", phone: "" },
      statuses: ["Pending", "Approved", "Open", "Closed", "Completed"],
    };
  },
    computed: {
    endDate() {
      if (!this.form.start_date || !this.form.duration) return "";
      const d = new Date(this.form.start_date);
      d.setUTCDate(d.getUTCDate() + this.form.duration - 1);
      return d.toISOString().slice(0, 10);
    },
  },
  mounted() { this.loadTab("overview"); },
  methods: {
    flash(msg, isError = false) {
      this.error = isError ? msg : ""; this.msg = isError ? "" : msg;
    },
    async loadTab(tab) {
      this.tab = tab; this.q = ""; this.flash("");
      await this.refresh();
    },
    async refresh() {
      const q = encodeURIComponent(this.q);
      try {
        if (this.tab === "overview") this.stats = await api("/api/admin/stats");
        if (this.tab === "treks") {
          this.treks = await api("/api/admin/treks?q=" + q);
          this.staff = await api("/api/admin/users?role=staff");
        }
        if (this.tab === "staff") this.staff = await api("/api/admin/users?role=staff&q=" + q);
        if (this.tab === "users") this.users = await api("/api/admin/users?role=user&q=" + q);
        if (this.tab === "bookings") this.bookings = await api("/api/admin/bookings?q=" + q);
      } catch (e) { this.flash(e.message, true); }
    },
    newTrek() { this.form = emptyTrek(); this.editingId = null; this.showForm = true; },
    editTrek(t) {
      this.form = { ...t }; this.editingId = t.id; this.showForm = true;
    },
    async saveTrek() {
      try {
        if (this.editingId) await api("/api/admin/treks/" + this.editingId, "PUT", this.form);
        else await api("/api/admin/treks", "POST", this.form);
        this.showForm = false; this.flash("Trek saved"); this.refresh();
      } catch (e) { this.flash(e.message, true); }
    },
    async deleteTrek(t) {
      if (!confirm("Delete " + t.name + "?")) return;
      try { await api("/api/admin/treks/" + t.id, "DELETE"); this.flash("Trek deleted"); this.refresh(); }
      catch (e) { this.flash(e.message, true); }
    },
    async assign(t, staffId) {
      try {
        await api("/api/admin/treks/" + t.id + "/assign", "PUT", { staff_id: staffId || null });
        this.flash("Staff updated"); this.refresh();
      } catch (e) { this.flash(e.message, true); }
    },
    async createStaff() {
      try {
        await api("/api/admin/staff", "POST", this.staffForm);
        this.staffForm = { name: "", email: "", password: "", phone: "" };
        this.flash("Staff created"); this.refresh();
      } catch (e) { this.flash(e.message, true); }
    },
    async setFlag(u, field) {
      const current = field === "is_blacklisted" ? u.is_blacklisted : u.is_active;
      try {
        await api("/api/admin/users/" + u.id + "/status", "PUT", { field, value: !current });
        this.refresh();
      } catch (e) { this.flash(e.message, true); }
    },
  },
  template: `
  <div class="container mt-4">
    <ul class="nav nav-pills mb-3">
      <li class="nav-item" v-for="t in ['overview','treks','staff','users','bookings']" :key="t">
        <a href="#" class="nav-link text-capitalize" :class="{active: tab===t}" @click.prevent="loadTab(t)">{{ t }}</a>
      </li>
    </ul>
    <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
    <div v-if="msg" class="alert alert-success py-2">{{ msg }}</div>

    <!-- Overview -->
    <div v-if="tab==='overview'" class="row g-3">
      <div class="col-6 col-md-3" v-for="(v,k) in stats" :key="k">
        <div class="card text-center shadow-sm"><div class="card-body">
          <h2>{{ v }}</h2><div class="text-muted text-capitalize">Total {{ k }}</div>
        </div></div>
      </div>
    </div>

    <!-- Search box for list tabs -->
    <div v-if="tab!=='overview' && !showForm" class="input-group mb-3">
      <input v-model="q" @keyup.enter="refresh" class="form-control" placeholder="Search...">
      <button class="btn btn-outline-secondary" @click="refresh">Search</button>
      <button v-if="tab==='treks'" class="btn btn-primary" @click="newTrek">+ New Trek</button>
    </div>

    <!-- Treks -->
    <div v-if="tab==='treks'">
      <form v-if="showForm" @submit.prevent="saveTrek" class="card card-body mb-3">
        <h5>{{ editingId ? 'Edit' : 'New' }} Trek</h5>
        <div class="row g-2">
          <div class="col-md-6"><input v-model="form.name" class="form-control" placeholder="Name" required></div>
          <div class="col-md-6"><input v-model="form.location" class="form-control" placeholder="Location" required></div>
          <div class="col-md-3"><select v-model="form.difficulty" class="form-select">
            <option>Easy</option><option>Moderate</option><option>Hard</option></select></div>
          <div class="col-md-3"><input v-model.number="form.duration" type="number" min="1" class="form-control" placeholder="Days" required></div>
          <div class="col-md-3"><input v-model.number="form.total_slots" type="number" min="1" class="form-control" placeholder="Slots" required></div>
          <div class="col-md-3"><select v-model="form.status" class="form-select">
            <option v-for="s in statuses" :key="s">{{ s }}</option></select></div>
          <div class="col-md-6"><input v-model="form.start_date" type="date" class="form-control"></div>
          <div class="col-md-6"><input :value="endDate" type="date" class="form-control" readonly title="End date is calculated from start date and days"></div>
          <div class="col-12"><textarea v-model="form.instructions" class="form-control" placeholder="Instructions"></textarea></div>
        </div>
        <div class="mt-3">
          <button class="btn btn-success me-2">Save</button>
          <button type="button" class="btn btn-secondary" @click="showForm=false">Cancel</button>
        </div>
      </form>
      <div class="table-responsive">
        <table class="table table-sm bg-white align-middle">
          <thead><tr><th>Name</th><th>Location</th><th>Diff.</th><th>Days</th><th>Slots</th><th>Status</th><th>Staff</th><th></th></tr></thead>
          <tbody>
            <tr v-for="t in treks" :key="t.id">
              <td>{{ t.name }}</td><td>{{ t.location }}</td><td>{{ t.difficulty }}</td><td>{{ t.duration }}</td>
              <td>{{ t.available_slots }}/{{ t.total_slots }}</td><td>{{ t.status }}</td>
              <td>
                <select class="form-select form-select-sm" :value="t.staff_id || ''" @change="assign(t, $event.target.value)">
                  <option value="">-- none --</option>
                  <option v-for="s in staff" :key="s.id" :value="s.id" :disabled="s.is_blacklisted">{{ s.name }}</option>
                </select>
              </td>
              <td class="text-nowrap">
                <button class="btn btn-sm btn-outline-primary me-1" @click="editTrek(t)">Edit</button>
                <button class="btn btn-sm btn-outline-danger" @click="deleteTrek(t)">Delete</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Staff -->
    <div v-if="tab==='staff'">
      <form @submit.prevent="createStaff" class="card card-body mb-3">
        <h5>Add Staff</h5>
        <div class="row g-2">
          <div class="col-md-3"><input v-model="staffForm.name" class="form-control" placeholder="Name" required></div>
          <div class="col-md-3"><input v-model="staffForm.email" type="email" class="form-control" placeholder="Email" required></div>
          <div class="col-md-2"><input v-model="staffForm.phone" class="form-control" placeholder="Phone"></div>
          <div class="col-md-2"><input v-model="staffForm.password" type="password" minlength="6" class="form-control" placeholder="Password" required></div>
          <div class="col-md-2"><button class="btn btn-success w-100">Add</button></div>
        </div>
      </form>
    </div>

    <!-- Staff and Users tables -->
    <div v-if="tab==='staff' || tab==='users'" class="table-responsive">
      <table class="table table-sm bg-white align-middle">
        <thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Status</th><th></th></tr></thead>
        <tbody>
          <tr v-for="u in (tab==='staff' ? staff : users)" :key="u.id">
            <td>{{ u.name }}</td><td>{{ u.email }}</td><td>{{ u.phone }}</td>
            <td>
              <span v-if="u.is_blacklisted" class="badge bg-danger">Blacklisted</span>
              <span v-else-if="!u.is_active" class="badge bg-warning text-dark">Deactivated</span>
              <span v-else class="badge bg-success">Active</span>
            </td>
            <td class="text-nowrap">
              <button class="btn btn-sm btn-outline-danger me-1" @click="setFlag(u,'is_blacklisted')">
                {{ u.is_blacklisted ? 'Unblacklist' : 'Blacklist' }}</button>
              <button class="btn btn-sm btn-outline-secondary" @click="setFlag(u,'is_active_user')">
                {{ u.is_active ? 'Deactivate' : 'Activate' }}</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Bookings -->
    <div v-if="tab==='bookings'" class="table-responsive">
      <table class="table table-sm bg-white">
        <thead><tr><th>#</th><th>User</th><th>Trek</th><th>Date</th><th>Status</th></tr></thead>
        <tbody>
          <tr v-for="b in bookings" :key="b.id">
            <td>{{ b.id }}</td><td>{{ b.user_name }}</td><td>{{ b.trek_name }}</td>
            <td>{{ b.booking_date }}</td><td>{{ b.status }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>`,
};

const StaffPanel = {
  data() {
    return { treks: [], error: "", msg: "" };
  },
  mounted() { this.load(); },
  methods: {
    flash(msg, isError = false) {
      this.error = isError ? msg : ""; this.msg = isError ? "" : msg;
    },
    async load() {
      try {
        const data = await api("/api/staff/treks");
        // new_slots / new_status hold what the staff is typing, before Save
        this.treks = data.map(t => ({
          ...t, new_slots: t.total_slots,
          new_status: t.status === "Closed" ? "Closed" : "Open",
          show: false, participants: [],
        }));
      } catch (e) { this.flash(e.message, true); }
    },
    canEdit(t) { return !["Pending", "Completed"].includes(t.status) && !t.is_started; },
    canStart(t) { return !t.is_started && ["Approved", "Open", "Closed"].includes(t.status); },
    async save(t) {
      try {
        await api("/api/staff/treks/" + t.id, "PUT", { total_slots: t.new_slots, status: t.new_status });
        this.flash("Trek updated"); this.load();
      } catch (e) { this.flash(e.message, true); }
    },
    async action(t, name) {          // name is 'start' or 'complete'
      try {
        await api("/api/staff/treks/" + t.id + "/" + name, "PUT");
        this.flash("Trek marked as " + name + (name === "start" ? "ed" : "d")); this.load();
      } catch (e) { this.flash(e.message, true); }
    },
    async toggleParticipants(t) {
      if (t.show) { t.show = false; return; }
      try {
        t.participants = await api("/api/staff/treks/" + t.id + "/participants");
        t.show = true;
      } catch (e) { this.flash(e.message, true); }
    },
  },
  template: `
  <div class="container mt-4">
    <h4 class="mb-3">My Assigned Treks</h4>
    <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
    <div v-if="msg" class="alert alert-success py-2">{{ msg }}</div>
    <p v-if="!treks.length" class="text-muted">No treks assigned to you yet.</p>

    <div class="card shadow-sm mb-3" v-for="t in treks" :key="t.id">
      <div class="card-body">
        <div class="d-flex justify-content-between">
          <h5>{{ t.name }} <small class="text-muted">{{ t.location }}</small></h5>
          <span class="badge bg-info text-dark align-self-start">
            {{ t.status }}<span v-if="t.is_started"> (started)</span>
          </span>
        </div>
        <p class="mb-2">{{ t.difficulty }} | {{ t.duration }} days | {{ t.start_date }} to {{ t.end_date }}
          | Registered: <b>{{ t.booked_count }}</b> | Available: {{ t.available_slots }}/{{ t.total_slots }}</p>

        <div v-if="canEdit(t)" class="row g-2 align-items-center mb-2">
          <div class="col-auto"><label class="col-form-label">Total slots</label></div>
          <div class="col-auto"><input v-model.number="t.new_slots" type="number" min="1" class="form-control form-control-sm" style="width:90px"></div>
          <div class="col-auto">
            <select v-model="t.new_status" class="form-select form-select-sm">
              <option>Open</option><option>Closed</option>
            </select>
          </div>
          <div class="col-auto"><button class="btn btn-sm btn-primary" @click="save(t)">Save</button></div>
        </div>
        <p v-if="t.status==='Pending'" class="text-muted small">Waiting for admin approval.</p>

        <button v-if="canStart(t)" class="btn btn-sm btn-warning me-2" @click="action(t,'start')">Mark Started</button>
        <button v-if="t.is_started && t.status!=='Completed'" class="btn btn-sm btn-success me-2" @click="action(t,'complete')">Mark Completed</button>
        <button class="btn btn-sm btn-outline-secondary" @click="toggleParticipants(t)">
          {{ t.show ? 'Hide' : 'View' }} Participants</button>

        <table v-if="t.show" class="table table-sm mt-3 mb-0">
          <thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Status</th></tr></thead>
          <tbody>
            <tr v-for="p in t.participants" :key="p.booking_id">
              <td>{{ p.name }}</td><td>{{ p.email }}</td><td>{{ p.phone }}</td><td>{{ p.status }}</td>
            </tr>
            <tr v-if="!t.participants.length"><td colspan="4" class="text-muted">No participants yet.</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>`,
};

const UserPanel = {
  data() {
    return {
      tab: "treks", treks: [], bookings: [], profile: { name: "", email: "", phone: "" },
      filters: { q: "", location: "", difficulty: "", max_days: "" },
      error: "", msg: "",exportFile: "",
    };
  },
  mounted() { this.loadTab("treks"); },
  methods: {
    flash(msg, isError = false) {
      this.error = isError ? msg : ""; this.msg = isError ? "" : msg;
    },
    async loadTab(tab) {
      this.tab = tab; this.flash("");
      try {
        if (tab === "treks") await this.loadTreks();
        if (tab === "bookings") this.bookings = await api("/api/user/bookings");
        if (tab === "profile") this.profile = await api("/api/user/profile");
      } catch (e) { this.flash(e.message, true); }
    },
    async loadTreks() {
      const params = new URLSearchParams();
      for (const [key, value] of Object.entries(this.filters)) {
        if (value) params.append(key, value);          // only send filters that are filled
      }
      this.treks = await api("/api/user/treks?" + params.toString());
    },
    async book(t) {
      try {
        await api("/api/user/treks/" + t.id + "/book", "POST");
        this.flash("Booked " + t.name); this.loadTreks();
      } catch (e) { this.flash(e.message, true); }
    },
    async cancel(b) {
      if (!confirm("Cancel booking for " + b.trek_name + "?")) return;
      try {
        await api("/api/user/bookings/" + b.id + "/cancel", "PUT");
        this.flash("Booking cancelled"); this.loadTab("bookings");
      } catch (e) { this.flash(e.message, true); }
    },
    async saveProfile() {
      try {
        this.profile = await api("/api/user/profile", "PUT", this.profile);
        this.flash("Profile updated");
      } catch (e) { this.flash(e.message, true); }
    },
    async exportCsv() {
      try {
        const data = await api("/api/user/export", "POST");
        this.exportFile = "";
        this.flash("Export started. You will get an alert when it is ready.");
        this.pollExport(data.task_id);
      } catch (e) { this.flash(e.message, true); }
    },
    pollExport(taskId) {
      // ask the server every 2 seconds whether the background job has finished
      const timer = setInterval(async () => {
        try {
          const r = await api("/api/user/export/" + taskId);
          if (r.state === "done") {
            clearInterval(timer);
            this.exportFile = r.file;
            alert("Your booking history export is ready!");
          } else if (r.state === "failed") {
            clearInterval(timer);
            this.flash("Export failed", true);
          }
        } catch (e) { clearInterval(timer); this.flash(e.message, true); }
      }, 2000);
    },
    async downloadCsv() {
      // a normal link cannot send the token header, so we fetch the file and save it ourselves
      const res = await fetch("/api/user/export/download/" + this.exportFile, {
        headers: { Authorization: "Bearer " + localStorage.getItem("token") },
      });
      const blob = await res.blob();
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = this.exportFile;
      link.click();
      URL.revokeObjectURL(link.href);
    },
    clearFilters() {
      this.filters = { q: "", location: "", difficulty: "", max_days: "" };
      this.loadTreks();
    },
  },
  template: `
  <div class="container mt-4">
    <ul class="nav nav-pills mb-3">
      <li class="nav-item" v-for="t in [['treks','Available Treks'],['bookings','My Bookings'],['profile','Profile']]" :key="t[0]">
        <a href="#" class="nav-link" :class="{active: tab===t[0]}" @click.prevent="loadTab(t[0])">{{ t[1] }}</a>
      </li>
    </ul>
    <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
    <div v-if="msg" class="alert alert-success py-2">{{ msg }}</div>

    <!-- Available treks -->
    <div v-if="tab==='treks'">
      <form class="row g-2 mb-3" @submit.prevent="loadTreks">
        <div class="col-md-3"><input v-model="filters.q" class="form-control" placeholder="Trek name"></div>
        <div class="col-md-3"><input v-model="filters.location" class="form-control" placeholder="Location"></div>
        <div class="col-md-2">
          <select v-model="filters.difficulty" class="form-select">
            <option value="">Any difficulty</option><option>Easy</option><option>Moderate</option><option>Hard</option>
          </select>
        </div>
        <div class="col-md-2"><input v-model="filters.max_days" type="number" min="1" class="form-control" placeholder="Max days"></div>
        <div class="col-md-2 d-flex gap-1">
          <button class="btn btn-primary flex-fill">Search</button>
          <button type="button" class="btn btn-outline-secondary" @click="clearFilters">Clear</button>
        </div>
      </form>
      <p v-if="!treks.length" class="text-muted">No treks found.</p>
      <div class="row g-3">
        <div class="col-md-6 col-lg-4" v-for="t in treks" :key="t.id">
          <div class="card h-100 shadow-sm"><div class="card-body d-flex flex-column">
            <h5>{{ t.name }}</h5>
            <div class="text-muted mb-2">{{ t.location }}</div>
            <div>{{ t.difficulty }} | {{ t.duration }} days</div>
            <div>{{ t.start_date }} to {{ t.end_date }}</div>
            <div class="mb-2">Slots left: <b>{{ t.available_slots }}</b> / {{ t.total_slots }}</div>
            <div v-if="t.instructions" class="small text-muted mb-2">{{ t.instructions }}</div>
            <div class="mt-auto">
              <span class="badge bg-info text-dark me-2">{{ t.status }}</span>
              <button v-if="t.already_booked" class="btn btn-sm btn-success" disabled>Booked</button>
              <button v-else class="btn btn-sm btn-primary" :disabled="t.status!=='Open' || t.available_slots<1" @click="book(t)">
                {{ t.available_slots < 1 ? 'Full' : (t.status==='Open' ? 'Book' : 'Not open yet') }}</button>
            </div>
          </div></div>
        </div>
      </div>
    </div>

    <!-- My bookings and history -->
    <div v-if="tab==='bookings'">
        <div class="mb-3">
        <button class="btn btn-outline-primary btn-sm me-2" @click="exportCsv">Export CSV</button>
        <button v-if="exportFile" class="btn btn-success btn-sm" @click="downloadCsv">Download CSV</button>
      </div>
      <div class="table-responsive">
      <table class="table table-sm bg-white align-middle">
        <thead><tr><th>Trek</th><th>Location</th><th>Dates</th><th>Booked on</th><th>Booking</th><th>Trek status</th><th></th></tr></thead>
        <tbody>
          <tr v-for="b in bookings" :key="b.id">
            <td>{{ b.trek_name }}</td><td>{{ b.location }}</td>
            <td>{{ b.start_date }} to {{ b.end_date }}</td><td>{{ b.booking_date }}</td>
            <td><span class="badge" :class="{'bg-success': b.booking_status==='Booked','bg-secondary': b.booking_status==='Cancelled','bg-primary': b.booking_status==='Completed'}">{{ b.booking_status }}</span></td>
            <td>{{ b.trek_status }}<span v-if="b.trek_started"> (started)</span></td>
            <td><button v-if="b.booking_status==='Booked' && !b.trek_started" class="btn btn-sm btn-outline-danger" @click="cancel(b)">Cancel</button></td>
          </tr>
          <tr v-if="!bookings.length"><td colspan="7" class="text-muted">No bookings yet.</td></tr>
        </tbody>
      </table>
    </div>
    </div>

    <!-- Profile -->
    <form v-if="tab==='profile'" @submit.prevent="saveProfile" class="card card-body" style="max-width:450px">
      <label class="form-label">Name</label>
      <input v-model="profile.name" class="form-control mb-3" required>
      <label class="form-label">Email (cannot be changed)</label>
      <input :value="profile.email" class="form-control mb-3" disabled>
      <label class="form-label">Phone</label>
      <input v-model="profile.phone" class="form-control mb-3">
      <button class="btn btn-primary">Save</button>
    </form>
  </div>`,
};

const Dashboard = {
  components: { AdminPanel, StaffPanel, UserPanel },
  props: ["user"],
  emits: ["logout"],
  template: `
  <nav class="navbar navbar-dark bg-dark px-3">
    <span class="navbar-brand">Trek App ({{ user.role }})</span>
    <button class="btn btn-outline-light btn-sm" @click="$emit('logout')">Logout</button>
  </nav>
  <AdminPanel v-if="user.role === 'admin'" />
  <StaffPanel v-else-if="user.role === 'staff'" />
  <UserPanel v-else />`,
};

createApp({
  components: { AuthPage, Dashboard },
  data() {
    return { user: JSON.parse(localStorage.getItem("user") || "null") };
  },
  methods: {
    logout() {
      localStorage.clear();
      this.user = null;
    },
  },
  template: `
    <Dashboard v-if="user" :user="user" @logout="logout" />
    <AuthPage v-else @logged-in="u => user = u" />`,
}).mount("#app");
