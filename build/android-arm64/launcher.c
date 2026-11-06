#define _GNU_SOURCE
#include <Python.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static int join_path(char *out, size_t n, const char *a, const char *b) {
    int r = snprintf(out, n, "%s/%s", a, b);
    return r > 0 && (size_t)r < n;
}
static int add_path(PyConfig *c, const char *p) {
    wchar_t *w = Py_DecodeLocale(p, NULL);
    if (!w) return 0;
    PyStatus s = PyWideStringList_Append(&c->module_search_paths, w);
    PyMem_RawFree(w);
    return !PyStatus_Exception(s);
}
int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "Usage: mtk <entry-script.py> [arguments...]\n");
        return 2;
    }
    char exe[PATH_MAX], bin[PATH_MAX], root[PATH_MAX];
    char home[PATH_MAX], stdlib[PATH_MAX], dynload[PATH_MAX];
    char site[PATH_MAX], app[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", exe, sizeof(exe)-1);
    if (n < 0) { perror("readlink"); return 1; }
    exe[n] = 0;
    char *slash = strrchr(exe, '/');
    if (!slash) return 1;
    *slash = 0;
    if (strlen(exe) >= sizeof(bin)) return 1;
    strcpy(bin, exe);
    strcpy(root, bin);
    slash = strrchr(root, '/');
    if (!slash) return 1;
    *slash = 0;
    if (!join_path(home,sizeof(home),root,"python")) {
        fprintf(stderr,"mtk: runtime path too long\\n"); return 1;
    }
    int stdlib_len = snprintf(stdlib,sizeof(stdlib),"%s/lib/python%d.%d",
                              home,PY_MAJOR_VERSION,PY_MINOR_VERSION);
    if (stdlib_len < 0 || (size_t)stdlib_len >= sizeof(stdlib) ||
        !join_path(dynload,sizeof(dynload),stdlib,"lib-dynload") ||
        !join_path(site,sizeof(site),home,"site-packages") ||
        !join_path(app,sizeof(app),root,"app")) {
        fprintf(stderr,"mtk: runtime path too long\\n"); return 1;
    }
    PyConfig c;
    PyConfig_InitIsolatedConfig(&c);
    c.use_environment = 0;
    c.user_site_directory = 0;
    c.site_import = 1;
    c.module_search_paths_set = 1;
    wchar_t *wh = Py_DecodeLocale(home,NULL);
    if (!wh) { PyConfig_Clear(&c); return 1; }
    PyStatus s = PyConfig_SetString(&c,&c.home,wh);
    PyMem_RawFree(wh);
    if (PyStatus_Exception(s) || !add_path(&c,stdlib) ||
        !add_path(&c,dynload) || !add_path(&c,site) || !add_path(&c,app)) {
        fprintf(stderr,"mtk: cannot configure Python paths\n");
        PyConfig_Clear(&c); return 1;
    }
    s = PyConfig_SetBytesArgv(&c,argc-1,argv+1);
    if (!PyStatus_Exception(s))
        s = PyConfig_SetBytesString(&c,&c.run_filename,argv[1]);
    if (PyStatus_Exception(s)) {
        fprintf(stderr,"mtk: Python config: %s\n",s.err_msg);
        PyConfig_Clear(&c); return 1;
    }
    s = Py_InitializeFromConfig(&c);
    PyConfig_Clear(&c);
    if (PyStatus_Exception(s)) {
        fprintf(stderr,"mtk: Python init: %s\n",s.err_msg);
        Py_ExitStatusException(s);
    }
    return Py_RunMain();
}
